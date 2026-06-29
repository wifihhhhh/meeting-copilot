from pathlib import Path

from scripts.run_extraction_experiments import CONFIGS, summarize


def test_all_ten_samples_have_annotations():
    samples = sorted(Path("data/samples").glob("meeting_*.txt"))
    assert len(samples) == 10
    assert all((Path("data/annotations") / f"{path.stem}_label.json").exists() for path in samples)


def test_extraction_matrix_has_rule_llm_and_hybrid():
    assert set(CONFIGS) == {"rules", "llm", "llm_plus_rules"}


def test_extraction_summary_averages_successful_rows():
    rows = [{
        "config": "rules", "status": "ok", "action_precision": 1, "action_recall": 0.5,
        "action_f1": 2 / 3, "decision_precision": 1, "decision_recall": 1,
        "decision_f1": 1, "field_completeness": 0.75, "latency_ms": 10,
    }]
    assert summarize(rows)[0]["mean_action_recall"] == 0.5
