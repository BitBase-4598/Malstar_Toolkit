import base64
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from config import MAX_JSON_UPLOAD_MB, WIKI_MAX_ZIP_MB
from db import get_connection
from logging_util import audit
from services.wiki import (
    create_page,
    delete_page,
    find_page_by_link,
    import_markdown_file,
    import_meta,
    import_vault_zip,
    list_pages,
    load_page,
    update_page,
    wiki_stored_path,
)

bp = Blueprint("wiki", __name__)


def _json_bytes(data):
    filename = str(data.get("filename") or "")
    raw = str(data.get("content") or data.get("contentBase64") or "")
    if not raw:
        return filename, None, "No file was uploaded."
    try:
        payload = base64.b64decode(raw, validate=False)
    except Exception:
        return filename, None, "The file data is not valid base64."
    if len(payload) > max(MAX_JSON_UPLOAD_MB, WIKI_MAX_ZIP_MB) * 1024 * 1024:
        return filename, None, f"JSON uploads are limited to {MAX_JSON_UPLOAD_MB} MB."
    return filename, payload, None


@bp.get("/api/wiki")
def wiki_list():
    q = str(request.args.get("q") or "").strip()
    with get_connection() as conn:
        pages = list_pages(conn, q)
        meta = import_meta(conn)
    return jsonify({"success": True, "data": pages, "meta": meta})


@bp.get("/api/wiki/<int:page_id>")
def wiki_get(page_id):
    with get_connection() as conn:
        data = load_page(conn, page_id)
    if not data:
        return jsonify({"success": False, "message": "Note not found"}), 404
    return jsonify({"success": True, "data": data})


@bp.get("/api/wiki/by-link")
def wiki_by_link():
    name = str(request.args.get("q") or request.args.get("title") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "A note name is required."}), 400
    with get_connection() as conn:
        data = find_page_by_link(conn, name)
        if data:
            data = load_page(conn, data["id"])
    if not data:
        return jsonify({"success": False, "message": "Note not found"}), 404
    return jsonify({"success": True, "data": data})


@bp.post("/api/wiki")
def wiki_create():
    body = request.get_json(silent=True) or {}
    title = str(body.get("title") or "").strip()
    if not title:
        audit("wiki.create", "failure", summary="missing title")
        return jsonify({"success": False, "message": "A title is required."}), 400
    with get_connection() as conn:
        data, error = create_page(
            conn,
            title,
            str(body.get("body") or ""),
            str(body.get("folder") or "Inbox"),
        )
    if error:
        audit("wiki.create", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    audit("wiki.create", resource_id=data["id"], summary=data["title"])
    return jsonify({"success": True, "message": "Note created", "data": data}), 201


@bp.patch("/api/wiki/<int:page_id>")
def wiki_update(page_id):
    body = request.get_json(silent=True) or {}
    with get_connection() as conn:
        data, error = update_page(
            conn,
            page_id,
            title=body.get("title"),
            body=body.get("body"),
            path=body.get("path"),
        )
    if error:
        audit("wiki.update", "failure", resource_id=page_id, summary=error)
        status = 404 if error == "Note not found." else 400
        return jsonify({"success": False, "message": error}), status
    audit("wiki.update", resource_id=page_id, summary=data["title"])
    return jsonify({"success": True, "message": "Note saved", "data": data})


@bp.delete("/api/wiki/<int:page_id>")
def wiki_delete(page_id):
    with get_connection() as conn:
        data, error = delete_page(conn, page_id)
    if error:
        audit("wiki.delete", "failure", resource_id=page_id, summary=error)
        return jsonify({"success": False, "message": error}), 404
    audit("wiki.delete", resource_id=page_id, summary=data["title"])
    return jsonify({"success": True, "message": "Note deleted"})


@bp.post("/api/wiki/import")
def wiki_import():
    replace = str(request.args.get("replace") or request.form.get("replace") or "").lower() in (
        "1",
        "true",
        "yes",
    )
    filename = ""
    payload = b""
    if "file" in request.files:
        uploaded = request.files["file"]
        filename = uploaded.filename or "vault.zip"
        payload = uploaded.read()
    else:
        filename, payload, error = _json_bytes(request.get_json(silent=True) or {})
        if error:
            audit("wiki.import", "failure", summary=error)
            return jsonify({"success": False, "message": error}), 400
    if Path(filename or "").suffix.lower() != ".zip":
        audit("wiki.import", "failure", summary="not a zip")
        return jsonify({"success": False, "message": "Import an Obsidian vault as a .zip file."}), 400
    with get_connection() as conn:
        data, error = import_vault_zip(conn, filename, payload, replace=replace)
    if error:
        audit("wiki.import", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    audit(
        "wiki.import",
        summary=f"file={data['filename']} pages={data['pageCount']} attachments={data['attachmentCount']}",
    )
    return jsonify({"success": True, "message": "Vault imported", "data": data})


@bp.post("/api/wiki/upload")
def wiki_upload_markdown():
    filename = ""
    payload = b""
    if "file" in request.files:
        uploaded = request.files["file"]
        filename = uploaded.filename or "Untitled.md"
        payload = uploaded.read()
    else:
        filename, payload, error = _json_bytes(request.get_json(silent=True) or {})
        if error:
            audit("wiki.upload", "failure", summary=error)
            return jsonify({"success": False, "message": error}), 400
    with get_connection() as conn:
        data, error = import_markdown_file(conn, filename, payload)
    if error:
        audit("wiki.upload", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    audit("wiki.upload", resource_id=data["id"], summary=data["title"])
    return jsonify({"success": True, "message": "Note uploaded", "data": data}), 201


@bp.get("/api/wiki/attachments/<int:attachment_id>")
def wiki_attachment(attachment_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM WikiAttachments WHERE ID=?",
            (attachment_id,),
        ).fetchone()
    if not row:
        return jsonify({"success": False, "message": "Attachment not found"}), 404
    path = wiki_stored_path(row["StoredName"])
    if not path.is_file():
        return jsonify({"success": False, "message": "Attachment is missing on disk"}), 404
    return send_file(path, download_name=row["OriginalName"], max_age=3600)
