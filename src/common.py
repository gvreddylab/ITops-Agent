"""
Central configuration – all values are overridable via .env or environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (if present)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

# ── Directories ──────────────────────────────────────────────────────────────
DOCS_DIR   = PROJECT_ROOT / "data" / "raw_docs"
CHROMA_DIR = PROJECT_ROOT / "index"

# ── ChromaDB ─────────────────────────────────────────────────────────────────
COLLECTION_NAME = "policies_procedures"

# ── Ollama ───────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL     = os.getenv("EMBED_MODEL",     "nomic-embed-text")
CHAT_MODEL      = os.getenv("CHAT_MODEL",      "llama3.1:8b")

# ── Retrieval tuning ──────────────────────────────────────────────────────────
CHUNK_TOKENS         = int(os.getenv("CHUNK_TOKENS",         "700"))
CHUNK_OVERLAP        = int(os.getenv("CHUNK_OVERLAP",        "120"))
TOP_K                = int(os.getenv("TOP_K",                "12"))
CONTEXT_CHUNKS_TO_LLM = int(os.getenv("CONTEXT_CHUNKS_TO_LLM", "6"))
DISTANCE_THRESHOLD   = float(os.getenv("DISTANCE_THRESHOLD", "1.2"))

# ── API ───────────────────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ── Conversation history ──────────────────────────────────────────────────────
HISTORY_TURNS = int(os.getenv("HISTORY_TURNS", "4"))
