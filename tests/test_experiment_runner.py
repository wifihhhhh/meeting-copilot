from scripts.run_experiments import ExperimentCase, evaluate_configuration, load_cases, summarize, write_outputs
from services.meeting_rag import RAGHit


class FakeRAG:
    similarity_threshold = None
    backend_name = "fake"

    def similarity_search(self, question, top_k, user_id):
        return [
            RAGHit("学分奖励", 1, "防诈骗", "", 0, 0.8, "real_dataset", "M3154"),
            RAGHit("其他内容", 2, "其他", "", 0, 0.4, "real_dataset", "M0001"),
        ][:top_k]


def test_load_real_cases_has_source_annotations():
    cases = load_cases("data/evaluation_questions/real_rag_questions.json")
    assert len(cases) == 20
    assert cases[0].expected_sources == ("M3311",)


def test_evaluate_and_summarize_source_metrics():
    case = ExperimentCase("有什么奖励", "学分奖励", "奖励", ("M3154", "M9999"))
    rows = evaluate_configuration(FakeRAG(), [case], provider="hash", top_k=3, threshold=0.3)
    assert rows[0]["source_hit"] == 1
    assert rows[0]["backend"] == "fake"
    assert rows[0]["recall_at_k"] == 0.5
    assert rows[0]["reference_coverage"] > 0
    summary = summarize(rows)[0]
    assert summary["source_hit_rate"] == 1.0
    assert summary["mean_recall_at_k"] == 0.5


def test_write_outputs(tmp_path):
    rows = evaluate_configuration(
        FakeRAG(),
        [ExperimentCase("有什么奖励", "学分奖励", "奖励", ("M3154",))],
        provider="hash",
        top_k=3,
        threshold=0.3,
    )
    paths = write_outputs(
        tmp_path,
        rows,
        {"generated_at": "2026-06-18", "dataset_size": 36, "question_count": 1, "unavailable_providers": {}},
    )
    assert all(path.exists() for path in paths)
    assert "来源命中率" in paths[2].read_text(encoding="utf-8")
