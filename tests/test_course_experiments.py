from scripts.run_course_experiments import RetrievalConfig, course_configs, retrieval_row
from scripts.run_experiments import ExperimentCase
from services.meeting_rag import RAGHit


def test_course_matrix_covers_required_ablations():
    configs = course_configs()
    assert {item.provider for item in configs} >= {"bge-m3", "nomic-embed-text"}
    assert {item.chunk_size for item in configs} >= {256, 512, 1024}
    assert {item.top_k for item in configs} >= {3, 5}
    assert {item.threshold for item in configs} >= {None, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7}
    assert {item.fallback_top_n for item in configs} >= {0, 1}


def test_retrieval_metrics_use_annotated_sources():
    case = ExperimentCase("问题", "答案", "事实型", ("M1", "M2"))
    config = RetrievalConfig("test", "测试", "hash", 512, 3, None, 0)
    hits = [
        RAGHit("x", None, "t", "", 0, 0.9, "real", "M0"),
        RAGHit("y", None, "t", "", 1, 0.8, "real", "M1"),
        RAGHit("z", None, "t", "", 2, 0.7, "real", "M2"),
    ]
    row = retrieval_row(1, case, config, hits, 1.0)
    assert row["source_hit"] == 1
    assert row["recall_at_k"] == 1.0
    assert row["mrr"] == 0.5
    assert 0 < row["ndcg_at_k"] < 1
