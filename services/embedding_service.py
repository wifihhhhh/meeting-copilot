import hashlib
import math
import re

from config import EMBEDDING_DIM


class HashEmbeddingFunction:
    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def __call__(self, input: list[str]) -> list[list[float]]:  # ChromaDB expects this argument name.
        return [hash_embedding(text, self.dim) for text in input]


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
