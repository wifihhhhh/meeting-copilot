from services.embedding_service import HashEmbeddingFunction


def test_embedding_function_supports_chromadb_query_interface():
    embedding = HashEmbeddingFunction(dim=8)
    assert embedding.embed_query(["hello"]) == embedding(["hello"])
