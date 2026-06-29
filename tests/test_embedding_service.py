import math

import pytest

from services.embedding_service import EmbeddingError, OllamaEmbeddingFunction


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append((url, json, timeout))
        return FakeResponse(self.payload)


def test_ollama_embedding_normalizes_vectors():
    session = FakeSession({"embeddings": [[3.0, 4.0]]})
    embedding = OllamaEmbeddingFunction(expected_dim=2, session=session)

    vector = embedding(["会议结论"])[0]

    assert vector == pytest.approx([0.6, 0.8])
    assert math.isclose(sum(value * value for value in vector), 1.0)
    assert session.calls[0][1]["model"] == "bge-m3"


def test_ollama_embedding_rejects_zero_vectors():
    embedding = OllamaEmbeddingFunction(
        expected_dim=2,
        session=FakeSession({"embeddings": [[0.0, 0.0]]}),
    )

    with pytest.raises(EmbeddingError, match="全零向量"):
        embedding(["会议结论"])


def test_ollama_embedding_rejects_wrong_dimension():
    embedding = OllamaEmbeddingFunction(
        expected_dim=3,
        session=FakeSession({"embeddings": [[1.0, 2.0]]}),
    )

    with pytest.raises(EmbeddingError, match="维度错误"):
        embedding(["会议结论"])
