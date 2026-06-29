import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import (
    BGE_EMBEDDING_MODEL,
    CHROMA_PATH,
    DEFAULT_EMBEDDING_PROVIDER,
    PROMPT_DIR,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_FALLBACK_TOP_N,
    RAG_SIMILARITY_THRESHOLD,
    RAG_TOP_K,
)
from database.repository import MeetingRepository
from services.embedding_service import HashEmbeddingFunction, OllamaEmbeddingFunction
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
    source: str = ""
    external_id: str = ""

    def to_source(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "title": self.title,
            "meeting_date": self.meeting_date,
            "chunk_index": self.chunk_index,
            "score": self.score,
            "source": self.source,
            "external_id": self.external_id,
        }


class MeetingRAG:
    """ChromaDB-backed RAG pipeline for historical meeting minutes."""

    def __init__(
        self,
        chroma_path: str | Path = CHROMA_PATH,
        collection_name: str | None = None,
        client: OllamaClient | None = None,
        repository: MeetingRepository | None = None,
        chunk_size: int = RAG_CHUNK_SIZE,
        chunk_overlap: int = RAG_CHUNK_OVERLAP,
        embedding_provider: str = DEFAULT_EMBEDDING_PROVIDER,
        embedding_model: str = BGE_EMBEDDING_MODEL,
        similarity_threshold: float | None = None,
        fallback_top_n: int = RAG_FALLBACK_TOP_N,
    ) -> None:
        self.chroma_path = Path(chroma_path)
        self.embedding_provider = embedding_provider.strip().lower()
        if self.embedding_provider not in {"hash", "bge-m3"}:
            raise ValueError("embedding_provider 必须是 'hash' 或 'bge-m3'。")
        self.embedding_model = embedding_model
        self.collection_name = collection_name or (
            "meeting_minutes" if self.embedding_provider == "hash" else "meeting_minutes_bge_m3_v1"
        )
        self.client = client or OllamaClient()
        self.repository = repository
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.similarity_threshold = similarity_threshold
        self.fallback_top_n = max(0, fallback_top_n)
        # Hybrid retrieval: keep dense embedding similarity as the main signal,
        # and add a lightweight BM25-style lexical score for exact names, dates,
        # task owners and project keywords. This avoids adding deployment
        # dependencies while reducing pure-vector misses on short queries.
        self.vector_weight = 0.78
        self.lexical_weight = 0.22
        self.embedding_function = (
            HashEmbeddingFunction()
            if self.embedding_provider == "hash"
            else OllamaEmbeddingFunction(model=self.embedding_model)
        )
        self.collection = self._init_collection()

    def embed(self, text: str) -> list[float]:
        self._validate_text(text, "待向量化文本")
        return self.embedding_function([text])[0]

    def index_meeting(
        self,
        meeting_id: int,
        title: str,
        meeting_date: str | None,
        minutes_markdown: str,
        user_id: int | None = None,
        is_shared: bool = False,
        source: str = "user",
        external_id: str = "",
    ) -> int:
        chunks = chunk_text(minutes_markdown, self.chunk_size, self.chunk_overlap)
        if not chunks:
            return 0

        self._delete_existing_meeting(meeting_id)
        ids = [self._chunk_id(meeting_id, index) for index in range(len(chunks))]
        documents = [self._format_index_document(title, meeting_date, chunk) for chunk in chunks]
        metadatas = [
            {
                "meeting_id": meeting_id,
                "title": title or "未命名会议",
                "meeting_date": meeting_date or "",
                "chunk_index": index,
                "user_id": user_id or 1,
                "is_shared": is_shared,
                "source": source,
                "external_id": external_id,
            }
            for index in range(len(chunks))
        ]
        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(chunks)

    def store_minutes(
        self,
        meeting_id: int,
        title: str,
        meeting_date: str | None,
        minutes_markdown: str,
        user_id: int | None = None,
        is_shared: bool = False,
        source: str = "user",
        external_id: str = "",
    ) -> int:
        return self.index_meeting(
            meeting_id,
            title,
            meeting_date,
            minutes_markdown,
            user_id=user_id,
            is_shared=is_shared,
            source=source,
            external_id=external_id,
        )

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
        where = self._build_where_clause(meeting_id=meeting_id, user_id=user_id)
        candidate_count = max(1, top_k * 3)
        result = self.collection.query(
            query_texts=[query],
            n_results=candidate_count,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        vector_hits = self._parse_hits(result)
        lexical_hits = self._lexical_search(query, where=where, top_k=max(top_k * 3, 10))
        hits = self._merge_hits(vector_hits, lexical_hits, top_k=max(top_k * 3, top_k))
        if self.similarity_threshold is None:
            return hits[:top_k]
        accepted = [hit for hit in hits if hit.score >= self.similarity_threshold]
        if accepted:
            return accepted[:top_k]
        return hits[: min(self.fallback_top_n, top_k)]

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
            collection_metadata = {
                "description": "Meeting minutes RAG collection",
                "embedding_provider": self.embedding_provider,
            }
            if self.embedding_provider == "bge-m3":
                collection_metadata["hnsw:space"] = "cosine"
            return chroma_client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata=collection_metadata,
            )
        except Exception as exc:
            raise VectorStoreUnavailableError(f"无法初始化 ChromaDB：{exc}") from exc

    def _delete_existing_meeting(self, meeting_id: int) -> None:
        try:
            self.collection.delete(where={"meeting_id": meeting_id})
        except Exception:
            pass

    @staticmethod
    def _build_where_clause(meeting_id: int | None = None, user_id: int | None = None) -> dict[str, Any] | None:
        visibility = {"$or": [{"user_id": user_id}, {"is_shared": True}]} if user_id is not None else None
        if meeting_id is not None and visibility is not None:
            return {"$and": [{"meeting_id": meeting_id}, visibility]}
        if meeting_id is not None:
            return {"meeting_id": meeting_id}
        if visibility is not None:
            return visibility
        return None

    def _lexical_search(self, query: str, where: dict[str, Any] | None, top_k: int) -> list[RAGHit]:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        try:
            result = self.collection.get(where=where, include=["documents", "metadatas"])
        except Exception:
            return []

        documents = self._flatten_collection_items(result.get("documents") or [])
        metadatas = self._flatten_collection_items(result.get("metadatas") or [])
        if not documents:
            return []

        searchable_texts = [
            self._searchable_text(document, metadata or {}) for document, metadata in zip(documents, metadatas)
        ]
        tokenized_docs = [self._tokenize(text) for text in searchable_texts]
        avg_doc_len = sum(len(tokens) for tokens in tokenized_docs) / max(len(tokenized_docs), 1)
        if avg_doc_len <= 0:
            return []

        document_frequency: Counter[str] = Counter()
        for tokens in tokenized_docs:
            document_frequency.update(set(tokens))

        raw_hits: list[tuple[float, str, dict[str, Any]]] = []
        query_terms = Counter(query_tokens)
        corpus_size = len(tokenized_docs)
        k1 = 1.5
        b = 0.75

        for document, metadata, tokens in zip(documents, metadatas, tokenized_docs):
            if not tokens:
                continue
            term_frequency = Counter(tokens)
            doc_len = len(tokens)
            score = 0.0
            for term, query_count in query_terms.items():
                frequency = term_frequency.get(term, 0)
                if frequency <= 0:
                    continue
                idf = math.log(1 + (corpus_size - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
                denominator = frequency + k1 * (1 - b + b * doc_len / avg_doc_len)
                score += query_count * idf * (frequency * (k1 + 1) / denominator)
            if score > 0:
                raw_hits.append((score, document, metadata or {}))

        if not raw_hits:
            return []

        max_score = max(score for score, _, _ in raw_hits) or 1.0
        hits: list[RAGHit] = []
        for score, document, metadata in sorted(raw_hits, key=lambda item: item[0], reverse=True)[:top_k]:
            hits.append(
                RAGHit(
                    content=document,
                    meeting_id=metadata.get("meeting_id"),
                    title=metadata.get("title") or "未命名会议",
                    meeting_date=metadata.get("meeting_date") or "",
                    chunk_index=int(metadata.get("chunk_index") or 0),
                    score=score / max_score,
                    source=str(metadata.get("source") or ""),
                    external_id=str(metadata.get("external_id") or ""),
                )
            )
        return hits

    def _merge_hits(self, vector_hits: list[RAGHit], lexical_hits: list[RAGHit], top_k: int) -> list[RAGHit]:
        merged: dict[tuple[int | None, int, str], RAGHit] = {}

        for hit in vector_hits:
            key = self._hit_key(hit)
            merged[key] = RAGHit(
                content=hit.content,
                meeting_id=hit.meeting_id,
                title=hit.title,
                meeting_date=hit.meeting_date,
                chunk_index=hit.chunk_index,
                score=hit.score * self.vector_weight,
                source=hit.source,
                external_id=hit.external_id,
            )

        for hit in lexical_hits:
            key = self._hit_key(hit)
            lexical_score = hit.score * self.lexical_weight
            if key in merged:
                merged[key].score = min(1.0, merged[key].score + lexical_score)
            else:
                merged[key] = RAGHit(
                    content=hit.content,
                    meeting_id=hit.meeting_id,
                    title=hit.title,
                    meeting_date=hit.meeting_date,
                    chunk_index=hit.chunk_index,
                    score=lexical_score,
                    source=hit.source,
                    external_id=hit.external_id,
                )

        return sorted(merged.values(), key=lambda hit: hit.score, reverse=True)[: max(1, top_k)]

    @staticmethod
    def _hit_key(hit: RAGHit) -> tuple[int | None, int, str]:
        return (hit.meeting_id, hit.chunk_index, hit.title)

    @staticmethod
    def _flatten_collection_items(items: list[Any]) -> list[Any]:
        if items and isinstance(items[0], list):
            return items[0]
        return items

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        lowered = text.lower()
        latin_tokens = re.findall(r"[a-z0-9_+\-.]+", lowered)
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        chinese_bigrams = [chinese_chars[index] + chinese_chars[index + 1] for index in range(len(chinese_chars) - 1)]
        return latin_tokens + chinese_chars + chinese_bigrams

    def _parse_hits(self, result: dict[str, Any]) -> list[RAGHit]:
        documents = result.get("documents", [[]])[0] or []
        metadatas = result.get("metadatas", [[]])[0] or []
        distances = result.get("distances", [[]])[0] or [0.0] * len(documents)
        hits: list[RAGHit] = []
        for document, metadata, distance in zip(documents, metadatas, distances):
            raw_distance = float(distance)
            score = max(0.0, 1.0 - raw_distance) if self.embedding_provider == "bge-m3" else 1.0 / (1.0 + raw_distance)
            hits.append(
                RAGHit(
                    content=document,
                    meeting_id=metadata.get("meeting_id"),
                    title=metadata.get("title") or "未命名会议",
                    meeting_date=metadata.get("meeting_date") or "",
                    chunk_index=int(metadata.get("chunk_index") or 0),
                    score=score,
                    source=str(metadata.get("source") or ""),
                    external_id=str(metadata.get("external_id") or ""),
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
    def _format_index_document(title: str, meeting_date: str | None, chunk: str) -> str:
        header = f"会议主题：{title or '未命名会议'}\n会议日期：{meeting_date or '未填写'}"
        return f"{header}\n\n{chunk}"

    @staticmethod
    def _searchable_text(document: str, metadata: dict[str, Any]) -> str:
        return f"{metadata.get('title') or ''}\n{metadata.get('meeting_date') or ''}\n{document}"

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
