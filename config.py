from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

APP_NAME = "Meeting Copilot"
DEFAULT_MODEL = "qwen2.5:1.5b"
OLLAMA_URL = "http://localhost:11434/api/generate"

DATABASE_PATH = BASE_DIR / "database" / "meeting_copilot.db"
CHROMA_PATH = BASE_DIR / "chroma_db"
EXPORT_DIR = BASE_DIR / "exports"
PROMPT_DIR = BASE_DIR / "prompts"

RAG_CHUNK_SIZE = 700
RAG_CHUNK_OVERLAP = 120
RAG_TOP_K = 5
EMBEDDING_DIM = 384

MIN_RAW_TEXT_LENGTH = 20
