from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from typing import Any

from config import DATA_DIR, EVALUATION_DIR
from services.evaluation_service import action_texts, decision_texts, fuzzy_precision_recall_f1
from services.meeting_extractor import MeetingExtractor
from services.ollama_client import OllamaClient


CONFIGS = {
    "rules": {"use_llm": False, "fallback_to_heuristic": True},
    "llm": {"use_llm": True, "fallback_to_heuristic": False},
    "llm_plus_rules": {"use_llm": True, "fallback_to_heuristic": True},
}


def run(output_dir: Path, model: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sample_dir = DATA_DIR / "samples"
    annotation_dir = DATA_DIR / "annotations"
    checkpoint = output_dir / "extraction_checkpoint.jsonl"
    completed: dict[str, dict[str, Any]] = {}
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            completed[item["run_key"]] = item
    extractor = MeetingExtractor(OllamaClient(model=model, timeout=600))
    pairs = []
    for raw_path in sorted(sample_dir.glob("meeting_*.txt")):
        gold_path = annotation_dir / f"{raw_path.stem}_label.json"
        if gold_path.exists():
            pairs.append((raw_path, gold_path))

    for config_name, options in CONFIGS.items():
        for raw_path, gold_path in pairs:
            run_key = f"{config_name}:{raw_path.stem}"
            if run_key in completed:
                continue
            raw_text = raw_path.read_text(encoding="utf-8")
            gold = json.loads(gold_path.read_text(encoding="utf-8"))
            started = time.perf_counter()
            try:
                predicted = extractor.extract(raw_text, **options).model_dump()
                action = fuzzy_precision_recall_f1(action_texts(predicted), action_texts(gold))
                decision = fuzzy_precision_recall_f1(decision_texts(predicted), decision_texts(gold))
                required = ["title", "date", "participants", "summary"]
                completeness = sum(bool(predicted.get(field)) for field in required) / len(required)
                item = {
                    "run_key": run_key,
                    "config": config_name,
                    "sample": raw_path.name,
                    "action_precision": action["precision"],
                    "action_recall": action["recall"],
                    "action_f1": action["f1"],
                    "decision_precision": decision["precision"],
                    "decision_recall": decision["recall"],
                    "decision_f1": decision["f1"],
                    "field_completeness": completeness,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    "status": "ok",
                    "error": "",
                }
            except Exception as exc:
                item = {
                    "run_key": run_key,
                    "config": config_name,
                    "sample": raw_path.name,
                    **{key: None for key in [
                        "action_precision", "action_recall", "action_f1", "decision_precision",
                        "decision_recall", "decision_f1", "field_completeness"
                    ]},
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    "status": "failed",
                    "error": str(exc),
                }
            completed[run_key] = item
            with checkpoint.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            print(f"extraction {run_key} {item['status']}", flush=True)
    rows = list(completed.values())
    summaries = summarize(rows)
    return rows, summaries


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["status"] == "ok":
            groups.setdefault(row["config"], []).append(row)
    metric_names = [
        "action_precision", "action_recall", "action_f1", "decision_precision",
        "decision_recall", "decision_f1", "field_completeness", "latency_ms"
    ]
    return [
        {"config": config, "samples": len(group)}
        | {f"mean_{metric}": round(statistics.fmean(float(row[metric]) for row in group), 6) for metric in metric_names}
        for config, group in groups.items()
    ]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def report(summaries: list[dict[str, Any]], model: str) -> str:
    lines = [
        "# 会议结构化抽取对比实验",
        "",
        f"模型：`{model}`；数据：10场人工标注会议；匹配：关键词覆盖模糊匹配。",
        "",
        "| 方法 | 样本 | 待办P | 待办R | 待办F1 | 决议P | 决议R | 决议F1 | 字段完整率 | 耗时ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summaries:
        lines.append(
            f"| {item['config']} | {item['samples']} | {item['mean_action_precision']} | {item['mean_action_recall']} | "
            f"{item['mean_action_f1']} | {item['mean_decision_precision']} | {item['mean_decision_recall']} | "
            f"{item['mean_decision_f1']} | {item['mean_field_completeness']} | {item['mean_latency_ms']} |"
        )
    lines += [
        "",
        "方法说明：`rules`为纯规则基线；`llm`为纯LLM结构化输出；`llm_plus_rules`在LLM失败时启用规则兜底。",
        "",
        "部署说明：根据待办与决议的分字段结果，正式系统已采用“待办使用LLM、决议优先规则”的字段级融合，并保留LLM异常时的整体规则兜底。该部署策略未作为表中的独立实验组重新评测，不能把两项最佳F1直接合成为新的分数。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate meeting extraction on 10 manually annotated samples.")
    parser.add_argument("--output-dir", default=str(EVALUATION_DIR / "course_final"))
    parser.add_argument("--model", default="qwen2.5:1.5b")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows, summaries = run(output_dir, args.model)
    write_csv(output_dir / "extraction_rows.csv", rows)
    write_csv(output_dir / "extraction_summary.csv", summaries)
    (output_dir / "extraction_report.md").write_text(report(summaries, args.model), encoding="utf-8")
    print(f"extraction_rows={len(rows)} output={output_dir}")
    return 0 if rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
