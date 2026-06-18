from typing import Any

from config import CHROMA_PATH, RAG_TOP_K
from services.embedding_service import HashEmbeddingFunction


class VectorStore:
    def __init__(self) -> None:
        self.available = False
        self.collection = None
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(CHROMA_PATH))
            self.collection = client.get_or_create_collection(
                name="meeting_minutes",
                embedding_function=HashEmbeddingFunction(),
                metadata={"description": "Historical meeting minutes chunks"},
            )
            self.available = True
        except Exception:
            self.available = False

    def upsert_meeting(self, meeting_id: int, title: str, meeting_date: str | None, chunks: list[str]) -> None:
        if not self.available or not self.collection:
            return
        ids = [f"meeting-{meeting_id}-{index}" for index in range(len(chunks))]
        metadatas = [
            {"meeting_id": meeting_id, "title": title, "meeting_date": meeting_date or "", "chunk_index": index}
            for index in range(len(chunks))
        ]
        self.collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)

    def query(self, question: str, top_k: int = RAG_TOP_K) -> list[dict[str, Any]]:
        if not self.available or not self.collection:
            return []
        result = self.collection.query(query_texts=[question], n_results=top_k)
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0] if result.get("distances") else [0] * len(documents)
        hits = []
        for doc, metadata, distance in zip(documents, metadatas, distances):
            hits.append({"content": doc, "metadata": metadata, "score": 1.0 / (1.0 + float(distance))})
        return hits
