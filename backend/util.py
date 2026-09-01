import re
from datetime import datetime


def now_stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def letters_only(value):
    return "".join(ch for ch in (value or "") if ch.isalpha()).casefold()


def fts_prefix_query(query, limit=8):
    tokens = re.findall(r"[A-Za-z0-9]+", query or "")
    if not tokens:
        return None
    return " OR ".join(f"{token}*" for token in tokens[:limit])
