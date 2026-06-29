from config import (
    DEFAULT_EMBEDDING_PROVIDER,
    DEFAULT_MODEL,
    FIELD_LEVEL_HYBRID_EXTRACTION,
    RAG_CHUNK_SIZE,
    RAG_SIMILARITY_THRESHOLD,
    RAG_TOP_K,
)


def test_recommended_runtime_defaults():
    assert DEFAULT_EMBEDDING_PROVIDER == "bge-m3"
    assert RAG_CHUNK_SIZE == 1024
    assert RAG_TOP_K == 5
    assert RAG_SIMILARITY_THRESHOLD == 0.30
    assert DEFAULT_MODEL == "qwen2.5:7b"
    assert FIELD_LEVEL_HYBRID_EXTRACTION is True
