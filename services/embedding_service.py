import hashlib
import math
import re
from typing import Any

import requests

from config import BGE_EMBEDDING_DIM, BGE_EMBEDDING_MODEL, EMBEDDING_DIM


class EmbeddingError(RuntimeError):
    """Raised when an embedding provider cannot return a valid vector."""


class HashEmbeddingFunction:
    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def __call__(self, input: list[str]) -> list[list[float]]:  # ChromaDB expects this argument name.
        return [hash_embedding(text, self.dim) for text in input]

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self(input)

    @staticmethod
    def name() -> str:
        return "meeting-copilot-hash-v1"


class OllamaEmbeddingFunction:
    def __init__(
        self,
        model: str = BGE_EMBEDDING_MODEL,
        base_url: str = "http://localhost:11434",
        timeout: float = 60.0,
        expected_dim: int = BGE_EMBEDDING_DIM,
        session: Any | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.expected_dim = expected_dim
        self.session = session or requests

    def __call__(self, input: list[str]) -> list[list[float]]:  # ChromaDB expects this argument name.
        texts = [str(text) for text in input]
        if not texts:
            return []
        try:
            response = self.session.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
                timeout=self.timeout,
            )
            response.raise_for_status()
            embeddings = response.json().get("embeddings")
        except Exception as exc:
            raise EmbeddingError(f"Ollama Embedding 请求失败：{exc}") from exc

        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise EmbeddingError("Ollama 没有返回与输入数量一致的 embeddings。")
        return [self._validate_and_normalize(vector) for vector in embeddings]

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def _validate_and_normalize(self, vector: Any) -> list[float]:
        if not isinstance(vector, list) or not vector:
            raise EmbeddingError("Embedding 为空或格式错误。")
        values = [float(value) for value in vector]
        if self.expected_dim and len(values) != self.expected_dim:
            raise EmbeddingError(f"Embedding 维度错误：期望 {self.expected_dim}，实际 {len(values)}。")
        norm = math.sqrt(sum(value * value for value in values))
        if norm <= 1e-12:
            raise EmbeddingError("Embedding 为全零向量，已拒绝写入向量库。")
        return [value / norm for value in values]

    def name(self) -> str:
        safe_model = re.sub(r"[^a-zA-Z0-9_-]+", "-", self.model).strip("-").lower()
        return f"meeting-copilot-ollama-{safe_model}-v1"


def hash_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    vector = [0.0] * dim
    tokens = tokenize(text)
    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % dim
        sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fa5]{1,2}", text.lower())
    return words or [text[:20]]
