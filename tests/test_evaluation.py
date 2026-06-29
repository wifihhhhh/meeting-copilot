from services.evaluation_service import fuzzy_precision_recall_f1, precision_recall_f1


def test_precision_recall_f1():
    scores = precision_recall_f1(["a", "b"], ["a", "c"])
    assert scores["precision"] == 0.5
    assert scores["recall"] == 0.5
    assert scores["f1"] == 0.5


def test_fuzzy_precision_recall_matches_semantically_overlapping_items():
    scores = fuzzy_precision_recall_f1(
        ["王工负责完成微服务拆分技术方案"],
        ["王工输出微服务拆分方案"],
        threshold=0.35,
    )

    assert scores["tp"] == 1
    assert scores["f1"] == 1.0
