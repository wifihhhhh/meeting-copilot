from __future__ import annotations

import argparse
import csv
import json
import math
import pickle
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from config import CHROMA_PATH, EVALUATION_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR
from database.repository import DEFAULT_USER_ID, MeetingRepository
from services.dataset_importer import DatasetImporter
from services.embedding_service import HashEmbeddingFunction, OllamaEmbeddingFunction
from services.evaluation_service import keyword_coverage_similarity
from services.meeting_rag import MeetingRAG, RAGHit, VectorStoreUnavailableError, chunk_text
from services.minutes_formatter import format_minutes
from services.schema_adapter import load_legacy_meeting


DEFAULT_QUESTION_FILE = Path(__file__).resolve().parents[1] / "data" / "evaluation_questions" / "real_rag_questions.json"


@dataclass(frozen=True)
class ExperimentCase:
    question: str
    reference: str
    category: str
    expected_sources: tuple[str, ...]


class InMemoryExperimentRAG:
    """Exact cosine-search fallback for experiments when ChromaDB is unavailable."""

    backend_name = "in_memory_exact_cosine"

    def __init__(
        self,
        provider: str,
        processed_dir: Path,
        raw_dir: Path,
        *,
        chunk_size: int = 700,
        chunk_overlap: int = 120,
        cache_path: str | Path | None = None,
    ) -> None:
        self.similarity_threshold: float | None = None
        self.fallback_top_n = 1
        if provider == "hash":
            self.embedding_function = HashEmbeddingFunction()
        elif provider == "bge-m3":
            self.embedding_function = OllamaEmbeddingFunction(model="bge-m3", expected_dim=1024, timeout=600)
        elif provider == "nomic-embed-text":
            self.embedding_function = OllamaEmbeddingFunction(model="nomic-embed-text", expected_dim=768, timeout=600)
        else:
            raise ValueError(f"不支持的 Embedding Provider：{provider}")
        if cache_path is not None and Path(cache_path).exists():
            with Path(cache_path).open("rb") as handle:
                self.records = pickle.load(handle)
            return
        self.records: list[tuple[RAGHit, list[float]]] = []
        pending: list[tuple[RAGHit, str]] = []
        for json_path in sorted(processed_dir.glob("M*.json")):
            adapted = load_legacy_meeting(json_path, raw_dir=raw_dir, source="real_dataset")
            markdown = format_minutes(adapted.minutes.model_dump())
            for index, content in enumerate(chunk_text(markdown, chunk_size, chunk_overlap)):
                pending.append(
                    (
                        RAGHit(
                            content=content,
                            meeting_id=None,
                            title=adapted.minutes.title,
                            meeting_date=adapted.minutes.date or "",
                            chunk_index=index,
                            score=0.0,
                            source=adapted.source,
                            external_id=adapted.external_id,
                        ),
                        content,
                    )
                )
        vectors = []
        texts = [content for _, content in pending]
        batch_size = 8
        for start in range(0, len(texts), batch_size):
            print(
                f"embedding provider={provider} chunk={chunk_size} batch={start // batch_size + 1}/"
                f"{math.ceil(len(texts) / batch_size)}",
                flush=True,
            )
            vectors.extend(self.embedding_function(texts[start : start + batch_size]))
        self.records = [(hit, vector) for (hit, _), vector in zip(pending, vectors)]
        if cache_path is not None:
            cache_path = Path(cache_path)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with cache_path.open("wb") as handle:
                pickle.dump(self.records, handle)

    def similarity_search(self, query: str, top_k: int, user_id: int | None = None) -> list[RAGHit]:
        del user_id
        return self.similarity_search_by_vector(self.embedding_function([query])[0], top_k)

    def similarity_search_by_vector(self, query_vector: list[float], top_k: int) -> list[RAGHit]:
        hits = []
        for template, vector in self.records:
            score = max(0.0, sum(left * right for left, right in zip(query_vector, vector)))
            hits.append(
                RAGHit(
                    content=template.content,
                    meeting_id=template.meeting_id,
                    title=template.title,
                    meeting_date=template.meeting_date,
                    chunk_index=template.chunk_index,
                    score=score,
                    source=template.source,
                    external_id=template.external_id,
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        candidate_count = max(1, top_k * 3 if self.similarity_threshold is not None else top_k)
        candidates = hits[:candidate_count]
        if self.similarity_threshold is None:
            return candidates[:top_k]
        accepted = [hit for hit in candidates if hit.score >= self.similarity_threshold]
        return accepted[:top_k] if accepted else candidates[: min(self.fallback_top_n, top_k)]


def load_cases(path: str | Path) -> list[ExperimentCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("RAG 评估集必须是非空 JSON 数组。")
    cases: list[ExperimentCase] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 条评估数据不是对象。")
        question = str(item.get("question") or "").strip()
        reference = str(item.get("reference") or item.get("expected") or "").strip()
        sources = tuple(str(value).strip() for value in item.get("expected_sources", []) if str(value).strip())
        if not question or not reference or not sources:
            raise ValueError(f"第 {index} 条评估数据缺少 question、reference 或 expected_sources。")
        cases.append(ExperimentCase(question, reference, str(item.get("category") or "未分类"), sources))
    return cases


def evaluate_configuration(
    rag: Any,
    cases: Iterable[ExperimentCase],
    *,
    provider: str,
    top_k: int,
    threshold: float,
    user_id: int = DEFAULT_USER_ID,
) -> list[dict[str, Any]]:
    rag.similarity_threshold = threshold
    rows: list[dict[str, Any]] = []
    for case_index, case in enumerate(cases, start=1):
        started = time.perf_counter()
        try:
            hits = rag.similarity_search(case.question, top_k=top_k, user_id=user_id)
            elapsed_ms = (time.perf_counter() - started) * 1000
            rows.append(_result_row(case_index, case, hits, provider, top_k, threshold, elapsed_ms, getattr(rag, "backend_name", "chromadb")))
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            rows.append(
                {
                    "case_id": case_index,
                    "provider": provider,
                    "backend": getattr(rag, "backend_name", "chromadb"),
                    "top_k": top_k,
                    "threshold": threshold,
                    "category": case.category,
                    "question": case.question,
                    "expected_sources": ";".join(case.expected_sources),
                    "retrieved_sources": "",
                    "retrieved_count": 0,
                    "source_hit": 0,
                    "recall_at_k": 0.0,
                    "reference_coverage": 0.0,
                    "average_similarity": 0.0,
                    "latency_ms": round(elapsed_ms, 3),
                    "status": "failed",
                    "error": str(exc),
                }
            )
    return rows


def _result_row(
    case_index: int,
    case: ExperimentCase,
    hits: list[RAGHit],
    provider: str,
    top_k: int,
    threshold: float,
    elapsed_ms: float,
    backend: str,
) -> dict[str, Any]:
    retrieved_sources = list(dict.fromkeys(hit.external_id for hit in hits if hit.external_id))
    expected = set(case.expected_sources)
    matched = expected & set(retrieved_sources)
    combined_context = "\n".join(hit.content for hit in hits)
    return {
        "case_id": case_index,
        "provider": provider,
        "backend": backend,
        "top_k": top_k,
        "threshold": threshold,
        "category": case.category,
        "question": case.question,
        "expected_sources": ";".join(case.expected_sources),
        "retrieved_sources": ";".join(retrieved_sources),
        "retrieved_count": len(hits),
        "source_hit": int(bool(matched)),
        "recall_at_k": round(len(matched) / len(expected), 6),
        "reference_coverage": round(keyword_coverage_similarity(combined_context, case.reference), 6),
        "average_similarity": round(statistics.fmean(hit.score for hit in hits), 6) if hits else 0.0,
        "latency_ms": round(elapsed_ms, 3),
        "status": "ok",
        "error": "",
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int, float], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row["provider"]), str(row["backend"]), int(row["top_k"]), float(row["threshold"]))
        groups.setdefault(key, []).append(row)
    summaries = []
    for (provider, backend, top_k, threshold), group in sorted(groups.items()):
        successful = [row for row in group if row["status"] == "ok"]
        summaries.append(
            {
                "provider": provider,
                "backend": backend,
                "top_k": top_k,
                "threshold": threshold,
                "questions": len(group),
                "successful": len(successful),
                "failed": len(group) - len(successful),
                "source_hit_rate": _mean(successful, "source_hit"),
                "mean_recall_at_k": _mean(successful, "recall_at_k"),
                "mean_reference_coverage": _mean(successful, "reference_coverage"),
                "mean_similarity": _mean(successful, "average_similarity"),
                "mean_retrieved_count": _mean(successful, "retrieved_count"),
                "mean_latency_ms": _mean(successful, "latency_ms"),
            }
        )
    return summaries


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    return round(statistics.fmean(float(row[key]) for row in rows), 6) if rows else None


def write_outputs(output_dir: str | Path, rows: list[dict[str, Any]], metadata: dict[str, Any]) -> tuple[Path, Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "rag_experiment_rows.csv"
    json_path = output_dir / "rag_experiment_summary.json"
    report_path = output_dir / "rag_experiment_report.md"
    fields = list(rows[0].keys()) if rows else []
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summaries = summarize(rows)
    json_path.write_text(
        json.dumps({"metadata": metadata, "configurations": summaries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path.write_text(_markdown_report(metadata, summaries), encoding="utf-8")
    return csv_path, json_path, report_path


def _markdown_report(metadata: dict[str, Any], summaries: list[dict[str, Any]]) -> str:
    lines = [
        "# RAG 正式对比实验报告",
        "",
        f"- 运行时间：{metadata['generated_at']}",
        f"- 真实会议：{metadata['dataset_size']} 场",
        f"- 评估问题：{metadata['question_count']} 条",
        "- 指标说明：来源命中率表示至少命中一个人工标注来源；Recall@K 衡量全部标注来源的覆盖；参考答案覆盖率为关键词覆盖基线，不等同于 LLM Judge。",
        "",
        "| Embedding | 检索后端 | Top-K | 阈值 | 成功/总数 | 来源命中率 | Recall@K | 答案覆盖率 | 平均相似度 | 实际返回数 | 平均耗时(ms) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summaries:
        lines.append(
            "| {provider} | {backend} | {top_k} | {threshold:.2f} | {successful}/{questions} | {source_hit_rate} | "
            "{mean_recall_at_k} | {mean_reference_coverage} | {mean_similarity} | {mean_retrieved_count} | {mean_latency_ms} |".format(
                **{key: ("N/A" if value is None else value) for key, value in item.items()}
            )
        )
    unavailable = metadata.get("unavailable_providers") or {}
    if unavailable:
        lines.extend(["", "## 未运行配置", ""])
        lines.extend(f"- `{provider}`：{reason}" for provider, reason in unavailable.items())
    lines.extend(["", "原始逐题结果见 `rag_experiment_rows.csv`，机器可读汇总见 `rag_experiment_summary.json`。", ""])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run reproducible RAG retrieval experiments on the 36-meeting dataset.")
    parser.add_argument("--questions", default=str(DEFAULT_QUESTION_FILE))
    parser.add_argument("--output-dir", default="")
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=["hash", "bge-m3", "nomic-embed-text"],
        default=["hash", "bge-m3"],
    )
    parser.add_argument("--top-k", nargs="+", type=int, default=[3, 5, 10])
    parser.add_argument("--thresholds", nargs="+", type=float, default=[0.20, 0.30, 0.40])
    parser.add_argument("--skip-index", action="store_true", help="Use existing experiment collections without rebuilding them.")
    parser.add_argument("--chroma-path", default=str(CHROMA_PATH))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if any(value <= 0 for value in args.top_k):
        raise ValueError("Top-K 必须大于 0。")
    cases = load_cases(args.questions)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if args.output_dir else EVALUATION_DIR / stamp
    rows: list[dict[str, Any]] = []
    unavailable: dict[str, str] = {}
    repository = MeetingRepository()

    for provider in args.providers:
        try:
            try:
                rag: Any = MeetingRAG(
                    repository=repository,
                    chroma_path=args.chroma_path,
                    collection_name=f"meeting_experiment_{provider.replace('-', '_')}_v1",
                    embedding_provider=provider,
                )
                if not args.skip_index:
                    imported = DatasetImporter(repository=repository, rag=rag).import_directory(
                        PROCESSED_DATA_DIR, RAW_DATA_DIR, source="real_dataset", shared=True
                    )
                    if imported.failed:
                        raise RuntimeError(f"索引失败 {imported.failed}/{imported.total}：{' | '.join(imported.errors[:3])}")
            except VectorStoreUnavailableError:
                rag = InMemoryExperimentRAG(provider, PROCESSED_DATA_DIR, RAW_DATA_DIR)
            for threshold in args.thresholds:
                for top_k in args.top_k:
                    rows.extend(
                        evaluate_configuration(
                            rag,
                            cases,
                            provider=provider,
                            top_k=top_k,
                            threshold=threshold,
                        )
                    )
        except Exception as exc:
            unavailable[provider] = str(exc)

    metadata = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dataset_size": len(list(PROCESSED_DATA_DIR.glob("M*.json"))),
        "question_count": len(cases),
        "question_file": str(Path(args.questions).resolve()),
        "unavailable_providers": unavailable,
    }
    csv_path, json_path, report_path = write_outputs(output_dir, rows, metadata)
    print(f"rows={len(rows)} csv={csv_path} json={json_path} report={report_path}")
    for provider, reason in unavailable.items():
        print(f"UNAVAILABLE {provider}: {reason}")
    return 0 if rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
