from pathlib import Path
from typing import Any

from config import CHROMA_PATH
from database.repository import MeetingRepository
from services.meeting_rag import MeetingRAG, chunk_text
from services.ollama_client import OllamaClient


class RAGService(MeetingRAG):
    """Backward-compatible wrapper around MeetingRAG."""

    def __init__(
        self,
        repository: MeetingRepository | None = None,
        vector_store: Any | None = None,
        client: OllamaClient | None = None,
        chroma_path: str | Path = CHROMA_PATH,
    ) -> None:
        super().__init__(
            chroma_path=chroma_path,
            client=client,
            repository=repository,
        )
