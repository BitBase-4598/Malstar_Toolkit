import base64
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from config import MAX_JSON_UPLOAD_MB
from db import get_connection
from logging_util import log_event
from services.files_store import (
    file_kind_from_name,
    file_to_dict,
    preview_docx,
    preview_xlsx,
    save_bytes_as_file,
    stored_path,
)
from services.rag import touch_index_state
from util import now_stamp

bp = Blueprint("files", __name__)


@bp.get("/api/files")
def list_files():
    q = str(request.args.get("q") or "").strip()
    with get_connection() as conn:
        if q:
            rows = conn.execute(
                """
                SELECT * FROM ToolkitFiles
                WHERE OriginalName LIKE ?
                ORDER BY UploadedAt DESC, ID DESC
                """,
                (f"%{q}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ToolkitFiles ORDER BY UploadedAt DESC, ID DESC"
            ).fetchall()
    return jsonify({"success": True, "data": [file_to_dict(row) for row in rows]})


def store_uploaded_file(filename, data):
    record, error = save_bytes_as_file(filename, data)
    if error:
        log_event("File upload failed", error)
        return jsonify({"success": False, "message": error}), 400
    log_event("File uploaded", f"{record['originalName']} ({record['kind']})")
    return jsonify({"success": True, "message": "File uploaded", "data": record}), 201


@bp.post("/api/files")
def upload_file():
    if "file" in request.files:
        file = request.files["file"]
        filename = file.filename or ""
        data = file.read()
        return store_uploaded_file(filename, data)
    data = request.get_json(silent=True) or {}
    filename = str(data.get("filename") or "")
    raw = str(data.get("content") or data.get("contentBase64") or "")
    if not raw:
        log_event("File upload failed", "no file uploaded")
        return jsonify({"success": False, "message": "No file was uploaded."}), 400
    try:
        payload = base64.b64decode(raw, validate=False)
    except Exception:
        return jsonify({"success": False, "message": "The file data is not valid base64."}), 400
    if len(payload) > MAX_JSON_UPLOAD_MB * 1024 * 1024:
        return jsonify({
            "success": False,
            "message": f"JSON uploads are limited to {MAX_JSON_UPLOAD_MB} MB. Use a smaller file.",
        }), 400
    return store_uploaded_file(filename, payload)


@bp.get("/api/files/<int:file_id>/preview")
def preview_file(file_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM ToolkitFiles WHERE ID=?", (file_id,)).fetchone()
    if not row:
        return jsonify({"success": False, "message": "File not found"}), 404
    path = stored_path(row["StoredName"])
    if not path.is_file():
        return jsonify({"success": False, "message": "File is missing on disk"}), 404
    try:
        preview = preview_docx(path) if row["Kind"] == "docx" else preview_xlsx(path)
    except Exception as error:
        return jsonify({"success": False, "message": f"Could not preview this file. {error}"}), 400
    preview["file"] = file_to_dict(row)
    return jsonify({"success": True, "data": preview})


@bp.get("/api/files/<int:file_id>")
def download_file(file_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM ToolkitFiles WHERE ID=?", (file_id,)).fetchone()
    if not row:
        return jsonify({"success": False, "message": "File not found"}), 404
    path = stored_path(row["StoredName"])
    if not path.is_file():
        return jsonify({"success": False, "message": "File is missing on disk"}), 404
    return send_file(path, as_attachment=True, download_name=row["OriginalName"])


@bp.patch("/api/files/<int:file_id>")
def rename_file(file_id):
    data = request.get_json(silent=True) or {}
    name = Path(str(data.get("originalName") or data.get("name") or "")).name.strip()
    if not name:
        return jsonify({"success": False, "message": "A file name is required."}), 400
    kind, suffix = file_kind_from_name(name)
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM ToolkitFiles WHERE ID=?", (file_id,)).fetchone()
        if not row:
            return jsonify({"success": False, "message": "File not found"}), 404
        if kind and kind != row["Kind"]:
            name = f"{Path(name).stem}{Path(row['StoredName']).suffix}"
        elif not Path(name).suffix:
            name = f"{name}{Path(row['StoredName']).suffix}"
        conn.execute(
            "UPDATE ToolkitFiles SET OriginalName=?, UpdatedAt=? WHERE ID=?",
            (name, now_stamp(), file_id),
        )
        conn.execute(
            "UPDATE RagChunks SET Title=? WHERE SourceType='file' AND SourceID=?",
            (name, file_id),
        )
        updated = conn.execute("SELECT * FROM ToolkitFiles WHERE ID=?", (file_id,)).fetchone()
    log_event("File renamed", f"id={file_id} {name}")
    return jsonify({"success": True, "message": "File renamed", "data": file_to_dict(updated)})


@bp.delete("/api/files/<int:file_id>")
def delete_file(file_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM ToolkitFiles WHERE ID=?", (file_id,)).fetchone()
        if not row:
            return jsonify({"success": False, "message": "File not found"}), 404
        attached = conn.execute(
            "SELECT SopID FROM SopAttachments WHERE FileID=? LIMIT 1",
            (file_id,),
        ).fetchone()
        if attached:
            return jsonify({
                "success": False,
                "message": "This file is attached to an SOP. Detach it first, then delete.",
            }), 409
        conn.execute("DELETE FROM RagChunks WHERE SourceType='file' AND SourceID=?", (file_id,))
        conn.execute("DELETE FROM ToolkitFiles WHERE ID=?", (file_id,))
        touch_index_state(conn)
    path = stored_path(row["StoredName"])
    if path.is_file():
        path.unlink()
    log_event("File deleted", f"id={file_id} {row['OriginalName']}")
    return jsonify({"success": True, "message": "File deleted"})
