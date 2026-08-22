import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _path(env_name, default):
    return Path(os.environ.get(env_name, default)).expanduser()


DB_PATH = _path("DATABASE_PATH", BASE_DIR / "customer_remark.db")
LOG_PATH = _path("LOG_PATH", BASE_DIR / "malstar_toolkit.log")
UPLOAD_DIR = _path("UPLOAD_DIR", BASE_DIR / "uploads")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "32"))
MAX_JSON_UPLOAD_MB = int(os.environ.get("MAX_JSON_UPLOAD_MB", "4"))
PREVIEW_ROWS = 200
PREVIEW_COLS = 30
ALLOWED_FILE_KINDS = {
    ".docx": "docx",
    ".xlsx": "xlsx",
}
RAG_CHUNK_SIZE = 600
RAG_CHUNK_OVERLAP = 80
RAG_TOP_K = 8
RAG_EXCERPT = 420
ASK_MAX_QUESTION = 800
DASHBOARD_MAX_ROWS = 5000
DASHBOARD_MISSING = {"", "—", "-", "–", "n/a", "na", "none", "null"}
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
AZURE_OPENAI_CHAT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "").strip()
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01").strip() or "2024-06-01"
AZURE_OPENAI_TIMEOUT = int(os.environ.get("AZURE_OPENAI_TIMEOUT", "25"))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
SCHEMA_VERSION = 2


def resolve_static_dir():
    env_path = os.environ.get("STATIC_DIR")
    if env_path:
        return Path(env_path)
    candidates = [
        BASE_DIR / "frontend" / "dist",
        BASE_DIR.parent / "frontend" / "dist",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


STATIC_DIR = resolve_static_dir()


def llm_enabled():
    return bool(AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY and AZURE_OPENAI_CHAT_DEPLOYMENT)
