import os
from pathlib import Path


def load_dotenv():
    if os.environ.get("MALSTAR_SKIP_DOTENV", "").strip().lower() in {"1", "true", "yes"}:
        return
    here = Path(__file__).resolve()
    for path in (here.parents[1] / ".env", here.parent / ".env"):
        if path.is_file():
            _apply(path)
            return


def _apply(path):
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_dotenv()
