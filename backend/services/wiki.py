import io
import json
import re
import uuid
import zipfile
from pathlib import Path

from flask import abort

from config import UPLOAD_DIR, WIKI_MAX_PAGES, WIKI_MAX_ZIP_MB
from util import now_stamp

SKIP_DIR_NAMES = {".obsidian", ".trash", ".git", "__macosx"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
WIKILINK_RE = re.compile(
    r"\[\[([^\]|#]+)(?:#([^\]|]+))?(?:\|([^\]]+))?\]\]"
)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def wiki_root():
    path = UPLOAD_DIR / "wiki"
    path.mkdir(parents=True, exist_ok=True)
    return path


def wiki_stored_path(stored_name):
    root = wiki_root().resolve()
    path = (root / stored_name).resolve()
    if path.parent != root:
        abort(404)
    return path


def normalize_vault_path(value):
    text = str(value or "").replace("\\", "/").strip().lstrip("/")
    parts = []
    for part in text.split("/"):
        lowered = part.strip().casefold()
        if not part or part in (".", "..") or lowered in SKIP_DIR_NAMES:
            if lowered in SKIP_DIR_NAMES:
                return ""
            continue
        if part.startswith("."):
            return ""
        parts.append(part.strip())
    return "/".join(parts)


def path_is_skipped(rel_path):
    parts = [part.casefold() for part in (rel_path or "").split("/") if part]
    return any(part in SKIP_DIR_NAMES or part.startswith(".") for part in parts)


def detect_vault_prefix(raw_names):
    rels = []
    for name in raw_names:
        rel = str(name or "").replace("\\", "/").strip("/")
        if rel:
            rels.append(rel)
    roots = {rel.split("/", 1)[0] for rel in rels if "/" in rel}
    files_at_root = [rel for rel in rels if "/" not in rel]
    if files_at_root or len(roots) != 1:
        return ""
    root = next(iter(roots))
    prefix = root.casefold() + "/"
    if any(
        item.casefold().startswith(prefix + ".obsidian/")
        or item.casefold().startswith(prefix + ".trash/")
        or item.casefold().startswith(prefix + ".git/")
        for item in rels
    ):
        return root
    return ""


def split_frontmatter(text):
    raw = text or ""
    match = FRONTMATTER_RE.match(raw)
    if not match:
        return {}, raw
    meta = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().casefold()
        if not key:
            continue
        meta[key] = value.strip().strip('"').strip("'")
    return meta, raw[match.end() :]


def title_from_note(path, meta, body):
    title = str(meta.get("title") or "").strip()
    if title:
        return title[:300]
    for line in (body or "").splitlines():
        heading = HEADING_RE.match(line.strip())
        if heading:
            return heading.group(2).strip()[:300]
    stem = Path(path).stem.replace("-", " ").replace("_", " ").strip()
    return (stem or "Untitled")[:300]


def folder_from_path(path):
    parent = str(Path(path).parent).replace("\\", "/")
    if parent in (".", ""):
        return ""
    return parent


def markdown_sections(body):
    sections = []
    heading = "overview"
    lines = []
    for line in (body or "").splitlines():
        match = HEADING_RE.match(line)
        if match:
            if lines:
                sections.append((heading, "\n".join(lines).strip()))
            heading = match.group(2).strip() or "overview"
            lines = [line]
        else:
            lines.append(line)
    if lines:
        sections.append((heading, "\n".join(lines).strip()))
    return [(name, text) for name, text in sections if text]


def page_to_dict(row, attachments=None, links=None):
    frontmatter = {}
    raw = row["Frontmatter"] or ""
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                frontmatter = parsed
        except json.JSONDecodeError:
            frontmatter = {}
    data = {
        "id": row["ID"],
        "path": row["Path"],
        "title": row["Title"],
        "folder": row["Folder"],
        "body": row["Body"],
        "frontmatter": frontmatter,
        "origin": row["Origin"],
        "createdAt": row["CreatedAt"],
        "updatedAt": row["UpdatedAt"],
    }
    if attachments is not None:
        data["attachments"] = attachments
    if links is not None:
        data["links"] = links
    return data


def attachment_to_dict(row):
    return {
        "id": row["ID"],
        "relPath": row["RelPath"],
        "originalName": row["OriginalName"],
        "kind": row["Kind"],
        "size": row["Size"],
        "url": f"/api/wiki/attachments/{row['ID']}",
    }


def list_attachments(conn, rel_paths=None):
    if rel_paths is None:
        rows = conn.execute(
            "SELECT * FROM WikiAttachments ORDER BY RelPath"
        ).fetchall()
    elif not rel_paths:
        return []
    else:
        placeholders = ",".join("?" for _ in rel_paths)
        rows = conn.execute(
            f"SELECT * FROM WikiAttachments WHERE RelPath IN ({placeholders}) ORDER BY RelPath",
            tuple(rel_paths),
        ).fetchall()
    return [attachment_to_dict(row) for row in rows]


def resolve_wikilinks(conn, body):
    names = []
    for match in WIKILINK_RE.finditer(body or ""):
        target = (match.group(1) or "").strip()
        if target and target not in names:
            names.append(target)
    links = []
    for name in names:
        page = find_page_by_link(conn, name)
        links.append({
            "title": name,
            "id": page["id"] if page else None,
            "path": page["path"] if page else "",
        })
    return links


def find_page_by_link(conn, name):
    target = str(name or "").strip()
    if not target:
        return None
    normalized = normalize_vault_path(target)
    candidates = []
    if normalized:
        if not normalized.lower().endswith(".md"):
            candidates.append(normalized + ".md")
        candidates.append(normalized)
    like = f"%{Path(target).name}%"
    row = None
    for path in candidates:
        row = conn.execute(
            "SELECT * FROM WikiPages WHERE lower(Path)=lower(?)",
            (path,),
        ).fetchone()
        if row:
            break
    if not row:
        row = conn.execute(
            """
            SELECT * FROM WikiPages
            WHERE lower(Title)=lower(?)
            ORDER BY ID DESC
            LIMIT 1
            """,
            (target,),
        ).fetchone()
    if not row:
        row = conn.execute(
            """
            SELECT * FROM WikiPages
            WHERE Path ILIKE ?
            ORDER BY ID DESC
            LIMIT 1
            """,
            (like,),
        ).fetchone()
    return page_to_dict(row) if row else None


def load_page(conn, page_id):
    row = conn.execute("SELECT * FROM WikiPages WHERE ID=?", (page_id,)).fetchone()
    if not row:
        return None
    folder = row["Folder"]
    if folder:
        attachments = conn.execute(
            """
            SELECT * FROM WikiAttachments
            WHERE RelPath = ? OR RelPath LIKE ?
            ORDER BY RelPath
            """,
            (row["Path"], folder + "/%"),
        ).fetchall()
    else:
        attachments = conn.execute(
            """
            SELECT * FROM WikiAttachments
            WHERE RelPath = ? OR RelPath NOT LIKE ?
            ORDER BY RelPath
            """,
            (row["Path"], "%/%"),
        ).fetchall()
    return page_to_dict(
        row,
        attachments=[attachment_to_dict(item) for item in attachments],
        links=resolve_wikilinks(conn, row["Body"]),
    )


def list_pages(conn, query=""):
    q = str(query or "").strip()
    if q:
        like = f"%{q}%"
        rows = conn.execute(
            """
            SELECT ID, Path, Title, Folder, Origin, CreatedAt, UpdatedAt
            FROM WikiPages
            WHERE Title ILIKE ? OR Path ILIKE ? OR Folder ILIKE ?
            ORDER BY Folder, Title, ID
            """,
            (like, like, like),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT ID, Path, Title, Folder, Origin, CreatedAt, UpdatedAt
            FROM WikiPages
            ORDER BY Folder, Title, ID
            """
        ).fetchall()
    return [
        {
            "id": row["ID"],
            "path": row["Path"],
            "title": row["Title"],
            "folder": row["Folder"],
            "origin": row["Origin"],
            "createdAt": row["CreatedAt"],
            "updatedAt": row["UpdatedAt"],
        }
        for row in rows
    ]


def unique_path(conn, desired, ignore_id=None):
    base = normalize_vault_path(desired) or "Inbox/Untitled.md"
    if not base.lower().endswith(".md"):
        base += ".md"
    stem = base[:-3]
    suffix = 1
    path = base
    while True:
        row = conn.execute(
            "SELECT ID FROM WikiPages WHERE lower(Path)=lower(?)",
            (path,),
        ).fetchone()
        if not row or (ignore_id and row["ID"] == ignore_id):
            return path
        suffix += 1
        path = f"{stem}-{suffix}.md"


def upsert_page(conn, path, body, origin="vault", title=None, keep_app_edits=True):
    from services.rag import index_wiki

    rel = normalize_vault_path(path)
    if not rel or not rel.lower().endswith(".md"):
        return None, "Markdown notes need a .md path."
    meta, content = split_frontmatter(body)
    note_title = (title or title_from_note(rel, meta, content)).strip()[:300]
    folder = folder_from_path(rel)
    stamp = now_stamp()
    existing = conn.execute(
        "SELECT * FROM WikiPages WHERE lower(Path)=lower(?)",
        (rel,),
    ).fetchone()
    if existing and keep_app_edits and existing["Origin"] == "app" and origin == "vault":
        return page_to_dict(existing), None
    payload = (
        rel,
        note_title,
        folder,
        content,
        json.dumps(meta, ensure_ascii=False),
        origin,
        stamp,
    )
    if existing:
        conn.execute(
            """
            UPDATE WikiPages
            SET Title=?, Folder=?, Body=?, Frontmatter=?, Origin=?, UpdatedAt=?
            WHERE ID=?
            """,
            (note_title, folder, content, json.dumps(meta, ensure_ascii=False), origin, stamp, existing["ID"]),
        )
        page_id = existing["ID"]
    else:
        cur = conn.execute(
            """
            INSERT INTO WikiPages (Path, Title, Folder, Body, Frontmatter, Origin, CreatedAt, UpdatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload + (stamp,),
        )
        page_id = cur.lastrowid
    index_wiki(conn, page_id)
    return load_page(conn, page_id), None


def create_page(conn, title, body="", folder="Inbox"):
    clean_title = str(title or "").strip() or "Untitled"
    folder_name = normalize_vault_path(folder) or "Inbox"
    slug = re.sub(r"[^\w\s.-]+", "", clean_title, flags=re.UNICODE).strip()
    slug = re.sub(r"\s+", " ", slug) or "Untitled"
    path = unique_path(conn, f"{folder_name}/{slug}.md")
    header = f"---\ntitle: {clean_title}\n---\n\n"
    text = body if str(body or "").startswith("---") else header + (body or f"# {clean_title}\n")
    return upsert_page(conn, path, text, origin="app", title=clean_title, keep_app_edits=False)


def update_page(conn, page_id, title=None, body=None, path=None):
    from services.rag import index_wiki

    row = conn.execute("SELECT * FROM WikiPages WHERE ID=?", (page_id,)).fetchone()
    if not row:
        return None, "Note not found."
    next_title = str(title if title is not None else row["Title"]).strip()[:300] or row["Title"]
    next_body = body if body is not None else row["Body"]
    next_path = row["Path"]
    if path is not None:
        next_path = unique_path(conn, path, ignore_id=page_id)
    meta, content = split_frontmatter(next_body)
    if title is not None:
        meta["title"] = next_title
    stamp = now_stamp()
    conn.execute(
        """
        UPDATE WikiPages
        SET Path=?, Title=?, Folder=?, Body=?, Frontmatter=?, Origin='app', UpdatedAt=?
        WHERE ID=?
        """,
        (
            next_path,
            next_title,
            folder_from_path(next_path),
            content,
            json.dumps(meta, ensure_ascii=False),
            stamp,
            page_id,
        ),
    )
    index_wiki(conn, page_id)
    return load_page(conn, page_id), None


def delete_page(conn, page_id):
    from services.rag import touch_index_state

    row = conn.execute("SELECT * FROM WikiPages WHERE ID=?", (page_id,)).fetchone()
    if not row:
        return None, "Note not found."
    conn.execute("DELETE FROM RagChunks WHERE SourceType='wiki' AND SourceID=?", (page_id,))
    conn.execute("DELETE FROM WikiPages WHERE ID=?", (page_id,))
    touch_index_state(conn)
    return page_to_dict(row), None


def save_attachment_bytes(conn, rel_path, data, original_name=""):
    rel = normalize_vault_path(rel_path)
    if not rel:
        return None, "Invalid attachment path."
    suffix = Path(rel).suffix.lower()
    kind = "image" if suffix in IMAGE_SUFFIXES else ""
    if not kind:
        return None, "Only PNG, JPEG, WebP, or GIF wiki images are stored."
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    dest = wiki_stored_path(stored_name)
    dest.write_bytes(data)
    stamp = now_stamp()
    name = Path(original_name or rel).name
    existing = conn.execute(
        "SELECT * FROM WikiAttachments WHERE lower(RelPath)=lower(?)",
        (rel,),
    ).fetchone()
    if existing:
        old = wiki_stored_path(existing["StoredName"])
        conn.execute(
            """
            UPDATE WikiAttachments
            SET StoredName=?, OriginalName=?, Kind=?, Size=?, UploadedAt=?
            WHERE ID=?
            """,
            (stored_name, name, kind, len(data), stamp, existing["ID"]),
        )
        if old.is_file() and old.name != stored_name:
            old.unlink()
        row = conn.execute("SELECT * FROM WikiAttachments WHERE ID=?", (existing["ID"],)).fetchone()
    else:
        cur = conn.execute(
            """
            INSERT INTO WikiAttachments (RelPath, StoredName, OriginalName, Kind, Size, UploadedAt)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (rel, stored_name, name, kind, len(data), stamp),
        )
        row = conn.execute("SELECT * FROM WikiAttachments WHERE ID=?", (cur.lastrowid,)).fetchone()
    return attachment_to_dict(row), None


def decode_text(data):
    if not data:
        return ""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def import_vault_zip(conn, filename, data, replace=False):
    if not data:
        return None, "The vault zip is empty."
    if len(data) > WIKI_MAX_ZIP_MB * 1024 * 1024:
        return None, f"Vault zip exceeds the {WIKI_MAX_ZIP_MB} MB limit."
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return None, "That file is not a valid zip archive."
    raw_names = [info.filename for info in archive.infolist() if not info.is_dir()]
    prefix = detect_vault_prefix(raw_names)
    names = []
    for info in archive.infolist():
        if info.is_dir():
            continue
        member_name = info.filename
        if prefix:
            root = prefix.replace("\\", "/").strip("/") + "/"
            alt = member_name.replace("\\", "/").lstrip("/")
            if alt.startswith(root):
                member_name = alt[len(root):]
            elif alt == prefix:
                continue
        rel = normalize_vault_path(member_name)
        if not rel or path_is_skipped(rel):
            continue
        names.append(rel)
    pages = 0
    attachments = 0
    skipped = 0
    imported_paths = []
    if len(names) > WIKI_MAX_PAGES:
        return None, f"Vault zip has more than {WIKI_MAX_PAGES} files."
    uncompressed = 0
    for info in archive.infolist():
        if info.is_dir():
            continue
        member_name = info.filename
        if prefix:
            root = prefix.replace("\\", "/").strip("/") + "/"
            alt = member_name.replace("\\", "/").lstrip("/")
            if alt.startswith(root):
                member_name = alt[len(root):]
            elif alt == prefix:
                continue
        rel = normalize_vault_path(member_name)
        if not rel or path_is_skipped(rel):
            continue
        uncompressed += max(info.file_size, 0)
        if uncompressed > WIKI_MAX_ZIP_MB * 1024 * 1024 * 4:
            return None, "Uncompressed vault is too large."
        payload = archive.read(info.filename)
        suffix = Path(rel).suffix.lower()
        if suffix == ".md":
            page, error = upsert_page(
                conn,
                rel,
                decode_text(payload),
                origin="vault",
                keep_app_edits=not replace,
            )
            if error or not page:
                skipped += 1
                continue
            if page.get("origin") == "app" and not replace:
                skipped += 1
            else:
                pages += 1
            imported_paths.append(rel)
        elif suffix in IMAGE_SUFFIXES:
            saved, error = save_attachment_bytes(conn, rel, payload, Path(rel).name)
            if error:
                skipped += 1
                continue
            attachments += 1
        else:
            skipped += 1
    if replace:
        if imported_paths:
            placeholders = ",".join("?" for _ in imported_paths)
            stale = conn.execute(
                f"""
                SELECT ID FROM WikiPages
                WHERE Origin='vault' AND Path NOT IN ({placeholders})
                """,
                tuple(imported_paths),
            ).fetchall()
        else:
            stale = conn.execute(
                "SELECT ID FROM WikiPages WHERE Origin='vault'"
            ).fetchall()
        for row in stale:
            delete_page(conn, row["ID"])
    stamp = now_stamp()
    conn.execute(
        """
        INSERT INTO WikiImportMeta (ID, Filename, ImportedAt, PageCount, AttachmentCount)
        VALUES (1, ?, ?, ?, ?)
        ON CONFLICT(ID) DO UPDATE SET
            Filename=excluded.Filename,
            ImportedAt=excluded.ImportedAt,
            PageCount=excluded.PageCount,
            AttachmentCount=excluded.AttachmentCount
        """,
        ((filename or "vault.zip")[:200], stamp, pages, attachments),
    )
    from services.rag import touch_index_state

    touch_index_state(conn)
    return {
        "filename": (filename or "vault.zip")[:200],
        "importedAt": stamp,
        "pageCount": pages,
        "attachmentCount": attachments,
        "skipped": skipped,
        "replace": bool(replace),
    }, None


def import_markdown_file(conn, filename, data):
    name = Path(filename or "Untitled.md").name
    if Path(name).suffix.lower() != ".md":
        return None, "Upload a .md note, a vault zip, or a DOCX/XLSX/image file."
    rel = unique_path(conn, f"Inbox/{name}")
    return upsert_page(conn, rel, decode_text(data), origin="app", keep_app_edits=False)


def import_meta(conn):
    row = conn.execute("SELECT * FROM WikiImportMeta WHERE ID=1").fetchone()
    if not row:
        return {"filename": "", "importedAt": "", "pageCount": 0, "attachmentCount": 0}
    return {
        "filename": row["Filename"],
        "importedAt": row["ImportedAt"],
        "pageCount": row["PageCount"],
        "attachmentCount": row["AttachmentCount"],
    }
