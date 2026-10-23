import os
from pathlib import Path

import envfile  # noqa: F401  # loads repo-root .env before reading DATABASE_URL

BASE_DIR = Path(__file__).resolve().parent


def _path(env_name, default):
    return Path(os.environ.get(env_name, default)).expanduser()


def _optional_path(env_name):
    raw = (os.environ.get(env_name) or "").strip()
    return Path(raw).expanduser() if raw else None


DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()
DB_PATH = _path("DATABASE_PATH", BASE_DIR / "malstar.db")
LOG_PATH = _path("LOG_PATH", BASE_DIR / "malstar_toolkit.log")
UPLOAD_DIR = _path("UPLOAD_DIR", BASE_DIR / "uploads")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "5"))
MAX_JSON_UPLOAD_MB = int(os.environ.get("MAX_JSON_UPLOAD_MB", "4"))
PREVIEW_ROWS = 200
PREVIEW_COLS = 30
ALLOWED_FILE_KINDS = {
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
}
IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
RAG_CHUNK_SIZE = 600
RAG_CHUNK_OVERLAP = 80
RAG_TOP_K = 8
RAG_EXCERPT = 420
ASK_MAX_QUESTION = 800
DASHBOARD_MAX_ROWS = 5000
# Optional spreadsheet/CSV seeds for CVM tools. Set via env when files exist.
LCL_XLSX_PATH = _optional_path("LCL_XLSX_PATH")
LCL_MAX_UPLOAD_MB = int(os.environ.get("LCL_MAX_UPLOAD_MB", "512"))
GCA_XLSX_PATH = _optional_path("GCA_XLSX_PATH")
UNLOCODE_CSV_PATH = _optional_path("UNLOCODE_CSV_PATH")
DE_LCL_XLSX_PATH = _optional_path("DE_LCL_XLSX_PATH")
BOSCH_DE_XLSX_PATH = _optional_path("BOSCH_DE_XLSX_PATH")
CASES_MAX_IMPORT_ROWS = int(os.environ.get("CASES_MAX_IMPORT_ROWS", "5000"))
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
# Shared CVM Basic Auth (empty password disables the gate). Read live in auth_gate.
TOOLKIT_BASIC_USER = (os.environ.get("TOOLKIT_BASIC_USER") or "malstar").strip() or "malstar"
TOOLKIT_BASIC_PASSWORD = (os.environ.get("TOOLKIT_BASIC_PASSWORD") or "").strip()
SCHEMA_VERSION = 13


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
