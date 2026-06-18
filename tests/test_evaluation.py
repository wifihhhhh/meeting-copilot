from services.evaluation_service import precision_recall_f1


def test_precision_recall_f1():
    scores = precision_recall_f1(["a", "b"], ["a", "c"])
    assert scores["precision"] == 0.5
    assert scores["recall"] == 0.5
    assert scores["f1"] == 0.5
