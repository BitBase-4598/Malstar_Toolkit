import os
import sqlite3
from pathlib import Path

import envfile  # noqa: F401  # loads repo-root .env before reading DATABASE_URL / DATABASE_PATH

IntegrityError = sqlite3.IntegrityError
OperationalError = sqlite3.OperationalError
DatabaseError = sqlite3.DatabaseError


def pk_autoincrement():
    return "INTEGER PRIMARY KEY AUTOINCREMENT"


def _sqlite_url_path(url):
    if url.lower().startswith("sqlite:///:memory:"):
        return ":memory:"
    if not url.lower().startswith("sqlite:///"):
        raise RuntimeError(
            "SQLite DATABASE_URL must look like sqlite:///relative.db or sqlite:////absolute/path.db"
        )
    return url[len("sqlite:///"):]


def resolve_db_path(db_path=None):
    if db_path:
        return Path(db_path).expanduser()
    url = (os.environ.get("DATABASE_URL") or "").strip()
    lowered = url.lower()
    if lowered.startswith("postgres"):
        raise RuntimeError(
            "PostgreSQL is no longer supported. Set DATABASE_PATH or DATABASE_URL=sqlite:///..."
        )
    if lowered.startswith("sqlite:"):
        parsed = _sqlite_url_path(url)
        if parsed == ":memory:":
            return parsed
        return Path(parsed).expanduser()
    env_path = (os.environ.get("DATABASE_PATH") or "").strip()
    if env_path:
        return Path(env_path).expanduser()
    from config import DB_PATH

    return DB_PATH


class Row:
    def __init__(self, mapping):
        if mapping is None:
            self._data = {}
            self._keys = []
            self._ci = {}
            return
        if hasattr(mapping, "keys"):
            self._keys = list(mapping.keys())
            self._data = {key: mapping[key] for key in self._keys}
        else:
            self._keys = list(range(len(mapping)))
            self._data = {index: value for index, value in enumerate(mapping)}
        self._ci = {str(key).lower(): value for key, value in self._data.items()}

    def __getitem__(self, key):
        if isinstance(key, int):
            if key in self._data:
                return self._data[key]
            return self._data[self._keys[key]]
        if key in self._data:
            return self._data[key]
        return self._ci[str(key).lower()]

    def keys(self):
        return self._keys

    def __contains__(self, key):
        if isinstance(key, int):
            return 0 <= key < len(self._keys)
        return key in self._data or str(key).lower() in self._ci


def wrap_row(row):
    if row is None:
        return None
    if isinstance(row, Row):
        return row
    return Row(row)


class CompatCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid = getattr(cursor, "lastrowid", None)

    @property
    def rowcount(self):
        return int(getattr(self._cursor, "rowcount", 0) or 0)

    def execute(self, sql, params=None):
        if params is None:
            self._cursor.execute(sql)
        else:
            self._cursor.execute(sql, tuple(params) if not isinstance(params, tuple) else params)
        self.lastrowid = self._cursor.lastrowid
        return self

    def executemany(self, sql, seq_of_params):
        self._cursor.executemany(sql, list(seq_of_params))
        return self

    def fetchone(self):
        return wrap_row(self._cursor.fetchone())

    def fetchall(self):
        return [wrap_row(row) for row in self._cursor.fetchall()]

    def __iter__(self):
        for row in self._cursor:
            yield wrap_row(row)

    def close(self):
        self._cursor.close()


class CompatConnection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return CompatCursor(self._conn.cursor())

    def execute(self, sql, params=None):
        cursor = self.cursor()
        return cursor.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        cursor = self.cursor()
        return cursor.executemany(sql, seq_of_params)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.rollback()
            else:
                self.commit()
        finally:
            self.close()
        return False


def connect(db_path=None):
    path = resolve_db_path(db_path)
    if path == ":memory:":
        conn = sqlite3.connect(":memory:", timeout=30)
    else:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-32768")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=134217728")
    return CompatConnection(conn)


def ping():
    with connect() as conn:
        conn.execute("SELECT 1")


def table_exists(conn, name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return bool(row)


def table_columns(conn, name):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({name})")}


def has_column(conn, table, column):
    columns = table_columns(conn, table)
    return column in columns or column.lower() in {str(item).lower() for item in columns}


def reset_identity(conn, *tables):
    names = ", ".join(f"'{name}'" for name in tables)
    try:
        conn.execute(f"DELETE FROM sqlite_sequence WHERE name IN ({names})")
    except sqlite3.DatabaseError:
        pass


def fetch_lastrowid(conn, cursor):
    return cursor.lastrowid
