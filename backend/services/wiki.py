import json
import math
import re
import urllib.error
import urllib.request

from config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_TIMEOUT,
    RAG_TOP_K,
    WIKI_SOURCE_LIMIT,
    embedding_enabled,
)
from db import get_connection
from db_engine import OperationalError
from services.rag import chunk_text, extract_docx_text, extract_xlsx_chunks
from services.files_store import stored_path
from services.sops import load_sop
from util import now_stamp

GUIDE_PAGES = (
    {
        "slug": "malstar-toolkit",
        "title": "MALSTAR Toolkit",
        "body": (
            "MALSTAR Toolkit is the internal ops workspace for remarks, leave, dashboards, "
            "files, SOPs, feedback cases, and Ask.\n\n"
            "Wiki is a searchable layer over the same site data. It does not copy every LCL "
            "shipment or UNLOCODE row. Those catalogs stay in SearchBar.\n\n"
            "Use Rebuild index after an import if new remarks, SOPs, files, cases, or GCA "
            "feedback should appear here."
        ),
    },
    {
        "slug": "ask-and-wiki",
        "title": "Ask and Wiki",
        "body": (
            "Ask searches SOP steps and uploaded DOCX or Excel files.\n"
            "Wiki adds customer remarks, cases, and GCA feedback excerpts, plus these guide pages.\n\n"
            "Keyword search uses PostgreSQL tsvector. If AZURE_OPENAI_EMBEDDING_DEPLOYMENT is set, "
            "chunk embeddings are stored as JSON and used to rerank matches. pgvector is optional; "
            "this test branch works without that extension."
        ),
    },
    {
        "slug": "remarks-and-search",
        "title": "Remarks and SearchBar",
        "body": (
            "SearchBar looks up CTRLOrgcode and customer letters on CustomerRemarks.\n"
            "Each remark is also a wiki page so Ask and Wiki can find Priority customer notes, "
            "weekly review text, and release instructions without opening the remarks grid.\n\n"
            "Demo rows seeded on an empty database: CQN / Demo Customer A, SHA / Demo Customer B, "
            "HKG / Demo Customer C."
        ),
    },
    {
        "slug": "leave-and-ops",
        "title": "Leave, Dashboard, and catalogs",
        "body": (
            "Leave Forecast stores people and monthly plans.\n"
            "Dashboard has Ops bookings, LCL volume, and GCA Hypercare.\n"
            "ICB stations and UNLOCODE stay as lookup tables. Wiki does not turn those 100k+ "
            "rows into articles."
        ),
    },
)

SOURCE_LABELS = {
    "guide": "Guide",
    "sop": "SOP",
    "file": "File",
    "remark": "Remark",
    "case": "Case",
    "gca_feedback": "GCA feedback",
}


def slugify(value):
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return text[:80] or "page"


def page_to_dict(row, include_body=True):
    payload = {
        "id": row["ID"],
        "slug": row["Slug"],
        "title": row["Title"],
        "sourceType": row["SourceType"],
        "sourceLabel": SOURCE_LABELS.get(row["SourceType"], row["SourceType"]),
        "sourceId": row["SourceID"],
        "updatedAt": row["UpdatedAt"],
    }
    if include_body:
        payload["body"] = row["Body"]
    return payload


def chunk_to_hit(row):
    return {
        "pageId": row["PageID"],
        "slug": row["Slug"],
        "title": row["Title"],
        "sourceType": row["SourceType"],
        "sourceLabel": SOURCE_LABELS.get(row["SourceType"], row["SourceType"]),
        "locator": row["Locator"],
        "excerpt": _excerpt(row["Body"]),
        "score": float(row["Score"]) if "Score" in row and row["Score"] is not None else 0,
    }


def _excerpt(body, limit=280):
    text = re.sub(r"\s+", " ", str(body or "")).strip()
    if len(text) <= limit:
        return text
    clipped = text[: limit - 1]
    space = clipped.rfind(" ")
    return (clipped[:space] if space > 80 else clipped) + "…"


def _tsquery(question):
    terms = re.findall(r"[A-Za-z0-9]{2,}", question or "")
    if not terms:
        return None
    return " | ".join(f"{term}:*" for term in terms[:24])


def _cosine(left, right):
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm_l = math.sqrt(sum(a * a for a in left))
    norm_r = math.sqrt(sum(b * b for b in right))
    if not norm_l or not norm_r:
        return 0.0
    return dot / (norm_l * norm_r)


def _parse_embedding(raw):
    if not raw:
        return None
    try:
        values = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(values, list) or not values:
        return None
    return [float(item) for item in values]


def embed_texts(texts):
    cleaned = [re.sub(r"\s+", " ", str(item or "")).strip()[:4000] for item in texts]
    if not embedding_enabled() or not any(cleaned):
        return [None] * len(texts)
    url = (
        f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_EMBEDDING_DEPLOYMENT}"
        f"/embeddings?api-version={AZURE_OPENAI_API_VERSION}"
    )
    payload = json.dumps({"input": [item or " " for item in cleaned]}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_API_KEY,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=AZURE_OPENAI_TIMEOUT) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return [None] * len(texts)
    by_index = {}
    for item in body.get("data") or []:
        try:
            by_index[int(item["index"])] = item.get("embedding")
        except (KeyError, TypeError, ValueError):
            continue
    return [by_index.get(index) for index in range(len(texts))]


def upsert_page(conn, slug, title, body, source_type, source_id=None, chunks=None):
    stamp = now_stamp()
    existing = conn.execute("SELECT ID FROM WikiPages WHERE Slug=?", (slug,)).fetchone()
    if existing:
        page_id = existing["ID"]
        conn.execute(
            """
            UPDATE WikiPages
            SET Title=?, Body=?, SourceType=?, SourceID=?, UpdatedAt=?
            WHERE ID=?
            """,
            (title, body, source_type, source_id, stamp, page_id),
        )
        conn.execute("DELETE FROM WikiChunks WHERE PageID=?", (page_id,))
    else:
        cur = conn.execute(
            """
            INSERT INTO WikiPages (Slug, Title, Body, SourceType, SourceID, UpdatedAt)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (slug, title, body, source_type, source_id, stamp),
        )
        page_id = cur.lastrowid
    pieces = chunks or [{"locator": "overview", "body": body}]
    vectors = embed_texts([item.get("body") or "" for item in pieces])
    for item, vector in zip(pieces, vectors):
        text = str(item.get("body") or "").strip()
        if not text:
            continue
        conn.execute(
            """
            INSERT INTO WikiChunks (PageID, Locator, Body, Embedding, UpdatedAt)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                page_id,
                str(item.get("locator") or "")[:120],
                text[:8000],
                json.dumps(vector) if vector else "",
                stamp,
            ),
        )
    return page_id


def _touch_state(conn):
    pages = conn.execute("SELECT COUNT(*) FROM WikiPages").fetchone()[0]
    chunks = conn.execute("SELECT COUNT(*) FROM WikiChunks").fetchone()[0]
    embedded = conn.execute(
        "SELECT COUNT(*) FROM WikiChunks WHERE Embedding != ''"
    ).fetchone()[0]
    conn.execute(
        """
        INSERT INTO WikiIndexState (ID, LastIndexedAt, PageCount, ChunkCount, EmbeddedCount)
        VALUES (1, ?, ?, ?, ?)
        ON CONFLICT (ID) DO UPDATE SET
            LastIndexedAt=excluded.LastIndexedAt,
            PageCount=excluded.PageCount,
            ChunkCount=excluded.ChunkCount,
            EmbeddedCount=excluded.EmbeddedCount
        """,
        (now_stamp(), pages, chunks, embedded),
    )


def ensure_demo_sop(conn):
    if conn.execute("SELECT COUNT(*) FROM Sops").fetchone()[0]:
        return
    stamp = now_stamp()
    cur = conn.execute(
        """
        INSERT INTO Sops (Title, Purpose, Owner, Revision, Status, CreatedAt, UpdatedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Book an LCL shipment",
            "Standard steps for an LCL booking in MALSTAR ops.",
            "MALSTAR",
            "1.0",
            "active",
            stamp,
            stamp,
        ),
    )
    sop_id = cur.lastrowid
    steps = [
        "Confirm the customer remark and any special handling notes in SearchBar.",
        "Check Leave Forecast if the controlling planner is out.",
        "Create the booking, then file the SOP attachment or rate sheet under Files.",
        "If GCA hypercare flags a wrong field, open Feedback and correct the HBL.",
    ]
    conn.executemany(
        "INSERT INTO SopSteps (SopID, StepNumber, Instruction) VALUES (?, ?, ?)",
        [(sop_id, index, text) for index, text in enumerate(steps, start=1)],
    )


def index_guides(conn):
    for page in GUIDE_PAGES:
        upsert_page(
            conn,
            page["slug"],
            page["title"],
            page["body"],
            "guide",
            chunks=[{"locator": "overview", "body": f"{page['title']}. {page['body']}"}],
        )


def index_sop_page(conn, sop_id):
    data = load_sop(conn, sop_id)
    if not data:
        return
    parts = [f"SOP: {data['title']}", f"Status: {data['status']}"]
    if data.get("purpose"):
        parts.append(data["purpose"])
    chunks = [{"locator": "overview", "body": " ".join(parts)}]
    for step in data.get("steps") or []:
        instruction = str(step.get("instruction") or "").strip()
        if instruction:
            chunks.append({
                "locator": f"step {step.get('stepNumber')}",
                "body": f"{data['title']} step {step.get('stepNumber')}: {instruction}",
            })
    upsert_page(
        conn,
        f"sop-{sop_id}",
        data["title"],
        "\n".join(item["body"] for item in chunks),
        "sop",
        sop_id,
        chunks,
    )


def index_file_page(conn, file_id):
    row = conn.execute("SELECT * FROM ToolkitFiles WHERE ID=?", (file_id,)).fetchone()
    if not row or row["Kind"] == "image":
        return
    title = row["OriginalName"]
    path = stored_path(row["StoredName"])
    if not path.is_file():
        return
    chunks = []
    if row["Kind"] == "docx":
        text = extract_docx_text(path)
        for index, piece in enumerate(chunk_text(text), start=1):
            chunks.append({"locator": f"section {index}", "body": f"{title}: {piece}"})
    elif row["Kind"] == "xlsx":
        chunks = [
            {"locator": item["locator"], "body": item["body"]}
            for item in extract_xlsx_chunks(path, title, file_id)[:80]
        ]
    if not chunks:
        return
    upsert_page(
        conn,
        f"file-{file_id}",
        title,
        "\n".join(item["body"] for item in chunks[:12]),
        "file",
        file_id,
        chunks,
    )


def index_remark_page(conn, row):
    title = f"{row['CTRLOrgcode']} / {row['Customer']}"
    body = "\n".join(
        part for part in (row["Remark1"], row["Remark2"], row["Remark3"]) if part
    ) or title
    upsert_page(
        conn,
        f"remark-{row['ID']}",
        title,
        body,
        "remark",
        row["ID"],
        [{"locator": "remarks", "body": f"{title}. {body}"}],
    )


def index_case_page(conn, row):
    title = row["HBL"] or row["Name"] or f"Case {row['ID']}"
    body = " ".join(
        str(row[name] or "")
        for name in (
            "Category",
            "Description",
            "WronglyIdentified",
            "Incorrect",
            "Corrected",
            "CauseOfError",
            "Action",
        )
    ).strip() or title
    upsert_page(
        conn,
        f"case-{row['ID']}",
        title,
        body,
        "case",
        row["ID"],
        [{"locator": "case", "body": f"Case {title}. {body}"}],
    )


def index_gca_feedback_page(conn, row):
    title = row["Hbl"] or row["HblKey"] or f"Feedback {row['ID']}"
    body = " ".join(
        str(row[name] or "")
        for name in (
            "Category",
            "WronglyIdentified",
            "Incorrect",
            "Corrected",
            "Cause",
            "Description",
            "Action",
        )
    ).strip() or title
    upsert_page(
        conn,
        f"gca-feedback-{row['ID']}",
        title,
        body,
        "gca_feedback",
        row["ID"],
        [{"locator": "feedback", "body": f"GCA feedback {title}. {body}"}],
    )


def rebuild_wiki(conn=None):
    own = conn is None
    if own:
        conn = get_connection()
        conn.__enter__()
    try:
        ensure_demo_sop(conn)
        conn.execute("DELETE FROM WikiChunks")
        conn.execute("DELETE FROM WikiPages")
        index_guides(conn)
        for row in conn.execute("SELECT ID FROM Sops ORDER BY ID").fetchall():
            index_sop_page(conn, row["ID"])
        for row in conn.execute("SELECT ID FROM ToolkitFiles ORDER BY ID").fetchall():
            index_file_page(conn, row["ID"])
        remarks = conn.execute(
            """
            SELECT ID, CTRLOrgcode, Customer, Remark1, Remark2, Remark3
            FROM CustomerRemarks
            ORDER BY UpdateTime DESC, ID DESC
            LIMIT ?
            """,
            (WIKI_SOURCE_LIMIT,),
        ).fetchall()
        for row in remarks:
            index_remark_page(conn, row)
        cases = conn.execute(
            "SELECT * FROM Cases ORDER BY UpdatedAt DESC, ID DESC LIMIT ?",
            (WIKI_SOURCE_LIMIT,),
        ).fetchall()
        for row in cases:
            index_case_page(conn, row)
        feedback = conn.execute(
            "SELECT * FROM GcaFeedback ORDER BY ID DESC LIMIT ?",
            (WIKI_SOURCE_LIMIT,),
        ).fetchall()
        for row in feedback:
            index_gca_feedback_page(conn, row)
        _touch_state(conn)
        return wiki_status(conn)
    finally:
        if own:
            conn.__exit__(None, None, None)


def wiki_status(conn):
    state = conn.execute("SELECT * FROM WikiIndexState WHERE ID=1").fetchone()
    by_type = {
        row["SourceType"]: row["N"]
        for row in conn.execute(
            "SELECT SourceType, COUNT(*) AS N FROM WikiPages GROUP BY SourceType"
        ).fetchall()
    }
    return {
        "pageCount": state["PageCount"] if state else 0,
        "chunkCount": state["ChunkCount"] if state else 0,
        "embeddedCount": state["EmbeddedCount"] if state else 0,
        "lastIndexedAt": state["LastIndexedAt"] if state else "",
        "embeddingEnabled": embedding_enabled(),
        "sources": {key: by_type.get(key, 0) for key in SOURCE_LABELS},
    }


def maybe_rebuild(conn):
    count = conn.execute("SELECT COUNT(*) FROM WikiPages").fetchone()[0]
    if count:
        return wiki_status(conn)
    return rebuild_wiki(conn)


def list_pages(query="", source_type="", page=1, page_size=40):
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 40), 1), 200)
    offset = (page - 1) * page_size
    clauses = []
    params = []
    if source_type:
        clauses.append("SourceType = ?")
        params.append(source_type)
    if query:
        like = f"%{query}%"
        clauses.append("(Title ILIKE ? OR Body ILIKE ? OR Slug ILIKE ?)")
        params.extend([like, like, like])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        maybe_rebuild(conn)
        total = conn.execute(f"SELECT COUNT(*) FROM WikiPages {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT ID, Slug, Title, SourceType, SourceID, UpdatedAt
            FROM WikiPages {where}
            ORDER BY CASE SourceType WHEN 'guide' THEN 0 ELSE 1 END, Title, ID
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        ).fetchall()
        status = wiki_status(conn)
    return {
        "data": [page_to_dict(row, include_body=False) for row in rows],
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": max((total + page_size - 1) // page_size, 1),
        },
        "meta": status,
    }


def get_page(slug):
    with get_connection() as conn:
        maybe_rebuild(conn)
        row = conn.execute("SELECT * FROM WikiPages WHERE Slug=?", (slug,)).fetchone()
        if not row:
            return None
        chunks = conn.execute(
            """
            SELECT Locator, Body FROM WikiChunks
            WHERE PageID=? ORDER BY ID
            """,
            (row["ID"],),
        ).fetchall()
    payload = page_to_dict(row)
    payload["chunks"] = [{"locator": item["Locator"], "body": item["Body"]} for item in chunks]
    return payload


def search_wiki(question, limit=RAG_TOP_K):
    query = (question or "").strip()
    if not query:
        return []
    tsquery = _tsquery(query)
    with get_connection() as conn:
        maybe_rebuild(conn)
        rows = []
        if tsquery:
            try:
                rows = conn.execute(
                    """
                    SELECT c.PageID, c.Locator, c.Body, c.Embedding,
                           p.Slug, p.Title, p.SourceType,
                           ts_rank(c.SearchTsv, to_tsquery('simple', ?)) AS Score
                    FROM WikiChunks c
                    JOIN WikiPages p ON p.ID = c.PageID
                    WHERE c.SearchTsv @@ to_tsquery('simple', ?)
                    ORDER BY Score DESC, c.ID
                    LIMIT ?
                    """,
                    (tsquery, tsquery, limit * 3),
                ).fetchall()
            except OperationalError:
                rows = []
        if not rows:
            like = f"%{query}%"
            rows = conn.execute(
                """
                SELECT c.PageID, c.Locator, c.Body, c.Embedding,
                       p.Slug, p.Title, p.SourceType,
                       0.1 AS Score
                FROM WikiChunks c
                JOIN WikiPages p ON p.ID = c.PageID
                WHERE c.Body ILIKE ? OR p.Title ILIKE ?
                ORDER BY c.ID DESC
                LIMIT ?
                """,
                (like, like, limit * 3),
            ).fetchall()
        query_vector = None
        if embedding_enabled():
            embedded = embed_texts([query])[0]
            query_vector = embedded
        scored = []
        for row in rows:
            lexical = float(row["Score"] or 0)
            vector = _parse_embedding(row["Embedding"])
            semantic = _cosine(query_vector, vector) if query_vector and vector else 0.0
            score = lexical + (semantic * 2)
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        hits = []
        seen = set()
        for score, row in scored:
            key = (row["PageID"], row["Locator"])
            if key in seen:
                continue
            seen.add(key)
            hits.append(chunk_to_hit({
                "PageID": row["PageID"],
                "Slug": row["Slug"],
                "Title": row["Title"],
                "SourceType": row["SourceType"],
                "Locator": row["Locator"],
                "Body": row["Body"],
                "Score": score,
            }))
            if len(hits) >= limit:
                break
        return hits


def search_wiki_chunks(conn, question, limit=RAG_TOP_K):
    hits = []
    for item in search_wiki(question, limit=limit):
        hits.append({
            "ID": item["pageId"],
            "SourceType": "wiki",
            "SourceID": item["pageId"],
            "Title": item["title"],
            "Locator": item["slug"],
            "Body": item["excerpt"],
        })
    return hits
