from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import CHROMA_PATH, PROMPT_DIR, RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE, RAG_TOP_K
from database.repository import MeetingRepository
from services.embedding_service import HashEmbeddingFunction, hash_embedding
from services.ollama_client import OllamaClient


class MeetingRAGError(Exception):
    """Base exception for MeetingRAG failures."""


class VectorStoreUnavailableError(MeetingRAGError):
    """Raised when ChromaDB cannot be initialized."""


@dataclass
class RAGHit:
    content: str
    meeting_id: int | None
    title: str
    meeting_date: str
    chunk_index: int
    score: float

    def to_source(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "title": self.title,
            "meeting_date": self.meeting_date,
            "chunk_index": self.chunk_index,
            "score": self.score,
        }


class MeetingRAG:
    """ChromaDB-backed RAG pipeline for historical meeting minutes."""

    def __init__(
        self,
        chroma_path: str | Path = CHROMA_PATH,
        collection_name: str = "meeting_minutes",
        client: OllamaClient | None = None,
        repository: MeetingRepository | None = None,
        chunk_size: int = RAG_CHUNK_SIZE,
        chunk_overlap: int = RAG_CHUNK_OVERLAP,
    ) -> None:
        self.chroma_path = Path(chroma_path)
        self.collection_name = collection_name
        self.client = client or OllamaClient()
        self.repository = repository
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_function = HashEmbeddingFunction()
        self.collection = self._init_collection()

    def embed(self, text: str) -> list[float]:
        self._validate_text(text, "待向量化文本")
        return hash_embedding(text)

    def index_meeting(
        self,
        meeting_id: int,
        title: str,
        meeting_date: str | None,
        minutes_markdown: str,
        user_id: int | None = None,
    ) -> int:
        chunks = chunk_text(minutes_markdown, self.chunk_size, self.chunk_overlap)
        if not chunks:
            return 0

        self._delete_existing_meeting(meeting_id)
        ids = [self._chunk_id(meeting_id, index) for index in range(len(chunks))]
        metadatas = [
            {
                "meeting_id": meeting_id,
                "title": title or "未命名会议",
                "meeting_date": meeting_date or "",
                "chunk_index": index,
                "user_id": user_id or 1,
            }
            for index in range(len(chunks))
        ]
        self.collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
        return len(chunks)

    def store_minutes(
        self,
        meeting_id: int,
        title: str,
        meeting_date: str | None,
        minutes_markdown: str,
        user_id: int | None = None,
    ) -> int:
        return self.index_meeting(meeting_id, title, meeting_date, minutes_markdown, user_id=user_id)

    def delete_meeting_index(self, meeting_id: int) -> None:
        self._delete_existing_meeting(meeting_id)

    def similarity_search(
        self,
        query: str,
        top_k: int = RAG_TOP_K,
        meeting_id: int | None = None,
        user_id: int | None = None,
    ) -> list[RAGHit]:
        self._validate_text(query, "检索问题")
        where = None
        if meeting_id is not None and user_id is not None:
            where = {"$and": [{"meeting_id": meeting_id}, {"user_id": user_id}]}
        elif meeting_id is not None:
            where = {"meeting_id": meeting_id}
        elif user_id is not None:
            where = {"user_id": user_id}
        result = self.collection.query(
            query_texts=[query],
            n_results=max(1, top_k),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        return self._parse_hits(result)

    def answer(
        self,
        question: str,
        top_k: int = RAG_TOP_K,
        use_llm: bool = True,
        meeting_id: int | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        hits = self.similarity_search(question, top_k=top_k, meeting_id=meeting_id, user_id=user_id)
        if not hits:
            answer = "历史会议中没有找到相关结论。"
            self._save_qa(question, answer, [], user_id=user_id)
            return {"answer": answer, "sources": [], "contexts": []}

        contexts = [hit.content for hit in hits]
        sources = [hit.to_source() for hit in hits]

        if use_llm:
            try:
                answer = self._generate_answer(question, contexts)
            except Exception:
                answer = self._fallback_answer(question, hits)
        else:
            answer = self._fallback_answer(question, hits)

        self._save_qa(question, answer, sources, user_id=user_id)
        return {"answer": answer, "sources": sources, "contexts": contexts}

    def _generate_answer(self, question: str, contexts: list[str]) -> str:
        template = (PROMPT_DIR / "rag_answer_prompt.md").read_text(encoding="utf-8")
        prompt = template.replace("{{QUESTION}}", question).replace("{{CONTEXT}}", "\n\n---\n\n".join(contexts))
        return self.client.generate(prompt, temperature=0.2)

    @staticmethod
    def _fallback_answer(question: str, hits: list[RAGHit]) -> str:
        best = hits[0]
        source = f"来源：{best.title} {best.meeting_date}".strip()
        return f"根据历史会议记录，和“{question}”最相关的内容是：\n\n{best.content[:700]}\n\n{source}"

    def _init_collection(self):
        try:
            import chromadb

            self.chroma_path.mkdir(parents=True, exist_ok=True)
            chroma_client = chromadb.PersistentClient(path=str(self.chroma_path))
            return chroma_client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"description": "Meeting minutes RAG collection"},
            )
        except Exception as exc:
            raise VectorStoreUnavailableError(f"无法初始化 ChromaDB：{exc}") from exc

    def _delete_existing_meeting(self, meeting_id: int) -> None:
        try:
            self.collection.delete(where={"meeting_id": meeting_id})
        except Exception:
            pass

    def _parse_hits(self, result: dict[str, Any]) -> list[RAGHit]:
        documents = result.get("documents", [[]])[0] or []
        metadatas = result.get("metadatas", [[]])[0] or []
        distances = result.get("distances", [[]])[0] or [0.0] * len(documents)
        hits: list[RAGHit] = []
        for document, metadata, distance in zip(documents, metadatas, distances):
            hits.append(
                RAGHit(
                    content=document,
                    meeting_id=metadata.get("meeting_id"),
                    title=metadata.get("title") or "未命名会议",
                    meeting_date=metadata.get("meeting_date") or "",
                    chunk_index=int(metadata.get("chunk_index") or 0),
                    score=1.0 / (1.0 + float(distance)),
                )
            )
        return hits

    def _save_qa(self, question: str, answer: str, sources: list[dict[str, Any]], user_id: int | None = None) -> None:
        if self.repository is not None:
            self.repository.save_qa(question, answer, sources, user_id=user_id)

    @staticmethod
    def _chunk_id(meeting_id: int, index: int) -> str:
        return f"meeting-{meeting_id}-chunk-{index}"

    @staticmethod
    def _validate_text(text: str, field_name: str) -> None:
        if not text or not text.strip():
            raise ValueError(f"{field_name}不能为空。")


def chunk_text(text: str, chunk_size: int = RAG_CHUNK_SIZE, overlap: int = RAG_CHUNK_OVERLAP) -> list[str]:
    clean = text.strip()
    if not clean:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0。")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap 必须大于等于 0 且小于 chunk_size。")

    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(start + chunk_size, len(clean))
        chunks.append(clean[start:end])
        if end == len(clean):
            break
        start = end - overlap
    return chunks
