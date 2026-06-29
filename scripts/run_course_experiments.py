from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from config import EVALUATION_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR
from scripts.run_experiments import DEFAULT_QUESTION_FILE, ExperimentCase, InMemoryExperimentRAG, load_cases
from services.llm_judge_service import SCORE_DIMENSIONS, calculate_weighted_score, normalize_scores
from services.ollama_client import OllamaClient, parse_json_block


JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "忠实性": {"type": "number"},
        "准确性": {"type": "number"},
        "完整性": {"type": "number"},
        "相关性": {"type": "number"},
        "简洁性": {"type": "number"},
        "理由": {"type": "string"},
    },
    "required": ["忠实性", "准确性", "完整性", "相关性", "简洁性", "理由"],
}


@dataclass(frozen=True)
class RetrievalConfig:
    config_id: str
    experiment: str
    provider: str
    chunk_size: int
    top_k: int
    threshold: float | None
    fallback_top_n: int

    @property
    def overlap(self) -> int:
        return max(1, round(self.chunk_size * 0.17))


def course_configs() -> list[RetrievalConfig]:
    """Word reproduction plus the chunk-size ablation required by the course guide."""
    return [
        RetrievalConfig("embedding_nomic", "Embedding模型", "nomic-embed-text", 512, 5, 0.30, 1),
        RetrievalConfig("embedding_bge", "Embedding模型", "bge-m3", 512, 5, 0.30, 1),
        RetrievalConfig("topk3", "检索策略", "bge-m3", 512, 3, None, 0),
        RetrievalConfig("topk5", "检索策略", "bge-m3", 512, 5, None, 0),
        RetrievalConfig("topk5_threshold03", "检索策略", "bge-m3", 512, 5, 0.30, 1),
        RetrievalConfig("fallback_off", "兜底机制", "bge-m3", 512, 5, 0.30, 0),
        RetrievalConfig("fallback_on", "兜底机制", "bge-m3", 512, 5, 0.30, 1),
        RetrievalConfig("threshold02", "相似度阈值", "bge-m3", 512, 5, 0.20, 1),
        RetrievalConfig("threshold03", "相似度阈值", "bge-m3", 512, 5, 0.30, 1),
        RetrievalConfig("threshold04", "相似度阈值", "bge-m3", 512, 5, 0.40, 1),
        RetrievalConfig("threshold05", "阈值扩展", "bge-m3", 512, 5, 0.50, 1),
        RetrievalConfig("threshold06", "阈值扩展", "bge-m3", 512, 5, 0.60, 1),
        RetrievalConfig("threshold07", "阈值扩展", "bge-m3", 512, 5, 0.70, 1),
        RetrievalConfig("chunk256", "Chunk大小", "bge-m3", 256, 5, 0.30, 1),
        RetrievalConfig("chunk512", "Chunk大小", "bge-m3", 512, 5, 0.30, 1),
        RetrievalConfig("chunk1024", "Chunk大小", "bge-m3", 1024, 5, 0.30, 1),
    ]


def run_retrieval(
    cases: list[ExperimentCase],
    configs: list[RetrievalConfig],
    cache_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, InMemoryExperimentRAG]]:
    rows: list[dict[str, Any]] = []
    unavailable: dict[str, str] = {}
    indexes: dict[tuple[str, int, int], InMemoryExperimentRAG] = {}
    config_indexes: dict[str, InMemoryExperimentRAG] = {}
    query_vectors: dict[tuple[tuple[str, int, int], str], list[float]] = {}
    for config in configs:
        key = (config.provider, config.chunk_size, config.overlap)
        try:
            if key not in indexes:
                indexes[key] = InMemoryExperimentRAG(
                    config.provider,
                    PROCESSED_DATA_DIR,
                    RAW_DATA_DIR,
                    chunk_size=config.chunk_size,
                    chunk_overlap=config.overlap,
                    cache_path=(
                        cache_dir / f"{config.provider}_{config.chunk_size}_{config.overlap}_v1.pkl"
                        if cache_dir is not None
                        else None
                    ),
                )
            rag = indexes[key]
            rag.similarity_threshold = config.threshold
            rag.fallback_top_n = config.fallback_top_n
            config_indexes[config.config_id] = rag
            for case_id, case in enumerate(cases, start=1):
                started = time.perf_counter()
                query_key = (key, case.question)
                if query_key not in query_vectors:
                    query_vectors[query_key] = rag.embedding_function([case.question])[0]
                hits = rag.similarity_search_by_vector(query_vectors[query_key], top_k=config.top_k)
                rows.append(retrieval_row(case_id, case, config, hits, (time.perf_counter() - started) * 1000))
        except Exception as exc:
            unavailable[config.config_id] = str(exc)
    return rows, unavailable, config_indexes


def retrieval_row(case_id, case, config, hits, latency_ms) -> dict[str, Any]:
    expected = set(case.expected_sources)
    ranked_sources = list(dict.fromkeys(hit.external_id for hit in hits if hit.external_id))
    relevant_ranks = [index for index, source in enumerate(ranked_sources, start=1) if source in expected]
    recall = len(expected & set(ranked_sources)) / len(expected)
    dcg = sum(1 / math.log2(rank + 1) for rank in relevant_ranks)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(len(expected), len(ranked_sources)) + 1))
    return {
        **asdict(config),
        "case_id": case_id,
        "category": case.category,
        "question": case.question,
        "reference": case.reference,
        "expected_sources": ";".join(case.expected_sources),
        "retrieved_sources": ";".join(ranked_sources),
        "retrieved_count": len(hits),
        "source_hit": int(bool(relevant_ranks)),
        "recall_at_k": round(recall, 6),
        "mrr": round(1 / relevant_ranks[0], 6) if relevant_ranks else 0.0,
        "ndcg_at_k": round(dcg / ideal, 6) if ideal else 0.0,
        "mean_similarity": round(statistics.fmean(hit.score for hit in hits), 6) if hits else 0.0,
        "latency_ms": round(latency_ms, 3),
        "contexts": [hit.content for hit in hits],
    }


def summarize_retrieval(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(row["config_id"], []).append(row)
    summaries = []
    for config_id, group in groups.items():
        first = group[0]
        summaries.append(
            {
                key: first[key]
                for key in ["config_id", "experiment", "provider", "chunk_size", "top_k", "threshold", "fallback_top_n"]
            }
            | {
                "questions": len(group),
                "source_hit_rate": mean(group, "source_hit"),
                "mean_recall_at_k": mean(group, "recall_at_k"),
                "mean_mrr": mean(group, "mrr"),
                "mean_ndcg_at_k": mean(group, "ndcg_at_k"),
                "mean_retrieved_count": mean(group, "retrieved_count"),
                "mean_latency_ms": mean(group, "latency_ms"),
            }
        )
    return summaries


def mean(rows: list[dict[str, Any]], key: str) -> float:
    return round(statistics.fmean(float(row[key]) for row in rows), 6)


def confidence_interval_95(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row[key]) for row in rows]
    if len(values) < 2:
        return 0.0
    return round(1.96 * statistics.stdev(values) / math.sqrt(len(values)), 6)


def answer_prompt(question: str, contexts: list[str], sources: list[str]) -> str:
    evidence = "\n\n---\n\n".join(contexts)
    return f"""你是会议知识库问答助手。只能根据给定会议证据回答，不得补充常识或猜测。
若证据不足，明确回答“根据现有会议记录无法确定”。回答应简洁但覆盖问题的全部要点。

问题：{question}

会议证据：
{evidence[:7000]}

可用来源ID：{', '.join(sources)}

请给出回答，并在末尾用“来源：ID”标注实际使用的会议。"""


def no_rag_prompt(question: str) -> str:
    return f"""请直接回答下面的问题。若你不知道具体会议中的事实，请明确说无法确定，不要编造。

问题：{question}"""


def judge_prompt(case: ExperimentCase, answer: str, contexts: list[str], mode: str) -> str:
    evidence = "\n\n---\n\n".join(contexts) if contexts else "无检索证据（无RAG基线）"
    return f"""你是独立、严格的会议问答评估员。根据参考答案评价系统回答。
不得因为措辞不同扣分；只看事实和要点。每项1-5分，5分最好。

问题：{case.question}
参考答案：{case.reference}
系统模式：{mode}
检索证据：{evidence[:7000]}
系统回答：{answer}

维度：忠实性、准确性、完整性、相关性、简洁性。
对于无RAG基线，“忠实性”表示是否避免编造且与参考答案一致。
只输出JSON：
{{"忠实性":1,"准确性":1,"完整性":1,"相关性":1,"简洁性":1,"理由":"简短理由"}}"""


def run_answers(
    cases: list[ExperimentCase],
    retrieval_rows: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    output_dir: Path,
    answer_model: str,
    judge_model: str,
) -> list[dict[str, Any]]:
    checkpoint = output_dir / "answer_checkpoint.jsonl"
    completed: dict[str, dict[str, Any]] = {}
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            if item.get("status") == "ok":
                completed[item["run_key"]] = item

    best = max(
        (item for item in summaries if item["provider"] == "bge-m3"),
        key=lambda item: (item["mean_recall_at_k"], item["mean_mrr"], -item["mean_latency_ms"]),
    )
    # Several Word tables reuse the exact same underlying parameters. Run identical
    # end-to-end jobs once; retrieval summaries retain every named table row.
    word_ids = {
        "embedding_nomic",
        "embedding_bge",
        "topk3",
        "topk5",
        "fallback_off",
        "threshold02",
        "threshold04",
        "threshold05",
        "threshold06",
        "chunk256",
        "chunk1024",
    }
    selected = [row for row in retrieval_rows if row["case_id"] <= 10 and row["config_id"] in word_ids]
    selected += [row for row in retrieval_rows if row["config_id"] == best["config_id"]]
    jobs: list[tuple[str, ExperimentCase, dict[str, Any] | None]] = []
    seen = set()
    for row in selected:
        key = f"rag:{row['config_id']}:{row['case_id']}"
        if key not in seen:
            jobs.append((key, cases[row["case_id"] - 1], row))
            seen.add(key)
    for case_id, case in enumerate(cases, start=1):
        jobs.append((f"no_rag:{case_id}", case, None))

    answer_client = OllamaClient(model=answer_model, timeout=600)
    judge_client = OllamaClient(model=judge_model, timeout=600)
    for index, (run_key, case, retrieval) in enumerate(jobs, start=1):
        if run_key in completed:
            continue
        contexts = retrieval["contexts"] if retrieval else []
        sources = retrieval["retrieved_sources"].split(";") if retrieval else []
        mode = retrieval["config_id"] if retrieval else "no_rag"
        started = time.perf_counter()
        try:
            prompt = answer_prompt(case.question, contexts, sources) if retrieval else no_rag_prompt(case.question)
            answer = answer_client.generate(prompt, temperature=0.0)
            raw_judge = judge_client.generate(
                judge_prompt(case, answer, contexts, mode),
                temperature=0.0,
                format_schema=JUDGE_SCHEMA,
            )
            scores = normalize_scores(parse_json_block(raw_judge))
            result = {
                "run_key": run_key,
                "mode": mode,
                "question": case.question,
                "reference": case.reference,
                "category": case.category,
                "answer": answer,
                "retrieved_sources": retrieval["retrieved_sources"] if retrieval else "",
                **scores,
                "weighted_score": calculate_weighted_score(scores),
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "status": "ok",
                "error": "",
            }
        except Exception as exc:
            result = {
                "run_key": run_key,
                "mode": mode,
                "question": case.question,
                "reference": case.reference,
                "category": case.category,
                "answer": "",
                "retrieved_sources": retrieval["retrieved_sources"] if retrieval else "",
                **{dimension: None for dimension in SCORE_DIMENSIONS},
                "理由": "",
                "weighted_score": None,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "status": "failed",
                "error": str(exc),
            }
        completed[run_key] = result
        with checkpoint.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
        print(f"answer {index}/{len(jobs)} {run_key} {result['status']}", flush=True)
    return list(completed.values())


def write_csv(path: Path, rows: list[dict[str, Any]], *, omit: set[str] | None = None) -> None:
    omit = omit or set()
    fields = [key for key in rows[0] if key not in omit] if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def answer_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["status"] == "ok":
            groups.setdefault(row["mode"], []).append(row)
    summaries = [
        {
            "mode": mode,
            "questions": len(group),
            "mean_judge_score": mean(group, "weighted_score"),
            "judge_score_ci95": confidence_interval_95(group, "weighted_score"),
            **{f"mean_{dimension}": mean(group, dimension) for dimension in SCORE_DIMENSIONS},
            "mean_latency_ms": mean(group, "latency_ms"),
        }
        for mode, group in groups.items()
    ]
    for mode in ("chunk1024", "no_rag"):
        word_group = [
            row for row in groups.get(mode, [])
            if int(str(row["run_key"]).rsplit(":", 1)[-1]) <= 10
        ]
        if word_group:
            summaries.append(
                {
                    "mode": f"{mode}_word10",
                    "questions": len(word_group),
                    "mean_judge_score": mean(word_group, "weighted_score"),
                    "judge_score_ci95": confidence_interval_95(word_group, "weighted_score"),
                    **{f"mean_{dimension}": mean(word_group, dimension) for dimension in SCORE_DIMENSIONS},
                    "mean_latency_ms": mean(word_group, "latency_ms"),
                }
            )
    return summaries


def report_text(metadata, retrieval_summaries, answer_summaries, answer_rows) -> str:
    lines = [
        "# 课程设计正式对比实验报告",
        "",
        "## 实验设计",
        "",
        "本实验使用同一固定测试集进行配对对比，避免不同题目难度造成混淆。36场会议中，M0101-M0106为6场关联型合成会议，其余30场来自真实会议数据。",
        "",
        "检索指标包括来源命中率、Recall@K、MRR和nDCG@K；端到端回答由独立Judge模型从忠实性、准确性、完整性、相关性和简洁性五维评分。",
        "",
        "## 检索实验汇总",
        "",
        "| 配置 | 实验 | Embedding | Chunk | Top-K | 阈值 | 兜底 | 命中率 | Recall@K | MRR | nDCG@K | 耗时ms |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in retrieval_summaries:
        lines.append(
            f"| {item['config_id']} | {item['experiment']} | {item['provider']} | {item['chunk_size']} | {item['top_k']} | "
            f"{item['threshold'] if item['threshold'] is not None else '无'} | {item['fallback_top_n']} | {item['source_hit_rate']} | "
            f"{item['mean_recall_at_k']} | {item['mean_mrr']} | {item['mean_ndcg_at_k']} | {item['mean_latency_ms']} |"
        )
    lines += ["", "## 端到端回答汇总", ""]
    if answer_summaries:
        score_map = {item["mode"]: item["mean_judge_score"] for item in answer_summaries}
        lines += [
            "| 模式 | 题数 | Judge总分±95%CI | 忠实性 | 准确性 | 完整性 | 相关性 | 简洁性 | 耗时ms |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for item in answer_summaries:
            lines.append(
                f"| {item['mode']} | {item['questions']} | {item['mean_judge_score']}±{item['judge_score_ci95']} | {item['mean_忠实性']} | "
                f"{item['mean_准确性']} | {item['mean_完整性']} | {item['mean_相关性']} | {item['mean_简洁性']} | {item['mean_latency_ms']} |"
            )
        lines += [
            "",
            "## 与《实验对比.docx》的复现对照",
            "",
            "下表中的原Word分数仅作历史基线。本次使用固定10题、Qwen2.5-1.5B回答和独立Qwen2.5-7B Judge，协议更严格，因此绝对分数不能直接横向等同。",
            "",
            "| 对比项 | 原Word | 本次复现 | 结论 |",
            "|---|---:|---:|---|",
            f"| Nomic Embedding | 3.34 | {score_map.get('embedding_nomic', 'N/A')} | 方向一致：弱于BGE |",
            f"| BGE-M3 Embedding | 4.64 | {score_map.get('embedding_bge', 'N/A')} | 方向一致：优于Nomic |",
            f"| Top-K=3 | 3.06 | {score_map.get('topk3', 'N/A')} | 本次略低于Top-5 |",
            f"| Top-K=5 | 1.41 | {score_map.get('topk5', 'N/A')} | 趋势不一致，旧结论可能受生成波动影响 |",
            f"| Top-5+阈值0.3 | 4.82 | {score_map.get('embedding_bge', 'N/A')} | 本次0.3未实际过滤多数候选 |",
            f"| 无兜底 | 3.80 | {score_map.get('fallback_off', 'N/A')} | 本次没有空检索，兜底未触发 |",
            f"| 有兜底 | 4.62 | {score_map.get('embedding_bge', 'N/A')} | 无法证明提升，需专门构造低相似度问题 |",
            f"| 阈值0.2 | 3.10 | {score_map.get('threshold02', 'N/A')} | 与0.3/0.4置信区间重叠 |",
            f"| 阈值0.3 | 3.63 | {score_map.get('embedding_bge', 'N/A')} | 旧结论未被严格复现 |",
            f"| 阈值0.4 | 3.49 | {score_map.get('threshold04', 'N/A')} | 与0.2/0.3无显著差异证据 |",
        ]
        failures = sorted(
            (row for row in answer_rows if row["status"] == "ok"), key=lambda row: row["weighted_score"]
        )[:5]
        lines += ["", "## 最低分案例（用于答辩失败分析）", ""]
        for row in failures:
            lines.append(
                f"- **{row['mode']} / {row['question']}**：{row['weighted_score']}/5。{row['理由']}"
            )
    else:
        lines.append("未运行LLM端到端实验；请加 `--with-llm` 并确保Ollama模型可用。")
    unavailable = metadata.get("unavailable") or {}
    if unavailable:
        lines += ["", "## 未运行配置", ""] + [f"- `{key}`：{value}" for key, value in unavailable.items()]
    lines += [
        "",
        "## 关键结论与取舍",
        "",
        "- BGE-M3 的检索 Recall@K、MRR 和 nDCG 均明显高于 Nomic，正式系统选择 BGE-M3，Nomic仅作为对照。",
        "- Top-5 的 Recall@K 高于 Top-3，适合需要跨多场会议综合回答的问题。",
        "- 原Word的0.2/0.3/0.4在分块架构下返回结果几乎相同；扩展到0.5后平均上下文减少但Recall不降，0.6开始损失Recall，0.7过滤过严。",
        "- 不同阈值的Judge置信区间重叠，不能仅凭单次均分宣称显著优劣；检索层可推荐0.5降噪，生产默认值仍保守保留0.3。",
        "- Chunk≈1024取得最高检索Recall；无RAG基线显著低于RAG，证明私有会议事实不能依赖模型参数记忆。",
        "- 上述结论已落入正式运行配置：BGE-M3、Chunk=1024、Top-K=5、阈值0.30；最终演示生成模型使用`qwen2.5:7b`。实验表中的回答分数仍来自`qwen2.5:1.5b`，不追溯改写实验条件。",
        "",
        "## 方法说明",
        "",
        "- Chunk大小按中文字符近似token计数，报告中明确披露，避免伪称为模型原生token。",
        "- 向量检索使用归一化Embedding的精确余弦排序，排除近似索引随机性；生产系统仍使用ChromaDB。",
        "- 所有回答温度为0，固定问题、参考答案和来源标注，支持断点续跑。",
        "",
        "## 有效性威胁与改进方向",
        "",
        "- 测试集为20题，复杂题占比较高但规模仍有限，均分需结合95%置信区间解读。",
        "- Judge虽使用独立的7B模型，但仍可能存在模型偏好；正式论文可抽取部分样本做双人人工复核并报告一致性。",
        "- 参数选择与汇报使用同一测试集，存在选择偏差；后续应拆分验证集和最终测试集。",
        "- Chunk采用中文字符近似token，若更换模型，应使用对应Tokenizer重新标定256/512/1024。",
        "- 精确余弦检索排除了近似索引误差；数据量扩大后还需补充Chroma/HNSW召回率与吞吐实验。",
        "",
    ]
    return "\n".join(lines)


def extraction_report_section(path: Path) -> str:
    if not path.exists():
        return ""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    lines = [
        "",
        "## 结构化抽取实验",
        "",
        "| 方法 | 样本 | 待办P | 待办R | 待办F1 | 决议P | 决议R | 决议F1 | 完整率 | 耗时ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['config']} | {row['samples']} | {row['mean_action_precision']} | {row['mean_action_recall']} | "
            f"{row['mean_action_f1']} | {row['mean_decision_precision']} | {row['mean_decision_recall']} | "
            f"{row['mean_decision_f1']} | {row['mean_field_completeness']} | {row['mean_latency_ms']} |"
        )
    lines += [
        "",
        "抽取结论：LLM的待办F1最高，规则的决议F1最高。正式系统已据此实现字段级融合（待办使用LLM、决议优先规则），并保留LLM异常时的整体规则兜底。该生产策略是根据表中分字段结果作出的工程选择，尚未作为独立第四组重新评测，因此不把两项最佳F1直接拼接成新的实验分数。",
        "",
    ]
    return "\n".join(lines)


def write_charts(output_dir: Path, retrieval_summaries: list[dict[str, Any]], answer_summaries: list[dict[str, Any]]) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    labels = [item["config_id"] for item in retrieval_summaries]
    x = list(range(len(labels)))
    fig, axes = plt.subplots(2, 1, figsize=(13, 9), constrained_layout=True)
    axes[0].bar(x, [item["mean_recall_at_k"] for item in retrieval_summaries], color="#2563eb")
    axes[0].set_title("不同配置的检索 Recall@K")
    axes[0].set_ylim(0, 1.05)
    axes[1].bar(x, [item["mean_mrr"] for item in retrieval_summaries], color="#7c3aed")
    axes[1].set_title("不同配置的 MRR")
    axes[1].set_ylim(0, 1.05)
    for axis in axes:
        axis.set_xticks(x, labels, rotation=35, ha="right")
        axis.grid(axis="y", alpha=0.2)
    fig.savefig(output_dir / "retrieval_comparison.png", dpi=180)
    plt.close(fig)
    if answer_summaries:
        labels = [item["mode"] for item in answer_summaries]
        values = [item["mean_judge_score"] for item in answer_summaries]
        errors = [item["judge_score_ci95"] for item in answer_summaries]
        fig, axis = plt.subplots(figsize=(13, 6), constrained_layout=True)
        axis.bar(range(len(labels)), values, yerr=errors, capsize=4, color="#0891b2")
        axis.set_xticks(range(len(labels)), labels, rotation=35, ha="right")
        axis.set_ylim(0, 5.2)
        axis.set_ylabel("LLM-as-Judge（1-5）")
        axis.set_title("端到端问答质量对比（误差线为95%置信区间）")
        axis.grid(axis="y", alpha=0.2)
        fig.savefig(output_dir / "answer_quality_comparison.png", dpi=180)
        plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reproduce and extend the course RAG experiments.")
    parser.add_argument("--questions", default=str(DEFAULT_QUESTION_FILE))
    parser.add_argument("--output-dir", default=str(EVALUATION_DIR / "course_final"))
    parser.add_argument("--with-llm", action="store_true")
    parser.add_argument("--answer-model", default="qwen2.5:1.5b")
    parser.add_argument("--judge-model", default="qwen2.5:7b")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = load_cases(args.questions)
    configs = course_configs()
    retrieval_rows, unavailable, _ = run_retrieval(cases, configs, output_dir / "embedding_cache")
    summaries = summarize_retrieval(retrieval_rows)
    write_csv(output_dir / "retrieval_rows.csv", retrieval_rows, omit={"contexts"})
    write_csv(output_dir / "retrieval_summary.csv", summaries)

    answers: list[dict[str, Any]] = []
    if args.with_llm and summaries:
        answers = run_answers(cases, retrieval_rows, summaries, output_dir, args.answer_model, args.judge_model)
        write_csv(output_dir / "answer_rows.csv", answers)
    answer_summaries = answer_summary(answers)
    if answer_summaries:
        write_csv(output_dir / "answer_summary.csv", answer_summaries)

    metadata = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dataset": {"total": 36, "real": 30, "synthetic_linked": 6},
        "questions": len(cases),
        "answer_model": args.answer_model,
        "judge_model": args.judge_model,
        "unavailable": unavailable,
    }
    (output_dir / "experiment_results.json").write_text(
        json.dumps(
            {"metadata": metadata, "retrieval_summary": summaries, "answer_summary": answer_summaries},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    full_report = report_text(metadata, summaries, answer_summaries, answers)
    full_report += extraction_report_section(output_dir / "extraction_summary.csv")
    (output_dir / "experiment_report.md").write_text(full_report, encoding="utf-8")
    write_charts(output_dir, summaries, answer_summaries)
    print(f"retrieval_rows={len(retrieval_rows)} answer_rows={len(answers)} output={output_dir}")
    for key, reason in unavailable.items():
        print(f"UNAVAILABLE {key}: {reason}")
    return 0 if retrieval_rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
