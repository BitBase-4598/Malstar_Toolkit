import base64
from pathlib import Path

from fastapi import APIRouter, Depends, Request

from config import MAX_JSON_UPLOAD_MB
from db import get_connection
from logging_util import audit
from services.files_store import (
    file_kind_from_name,
    file_to_dict,
    image_mime_type,
    preview_docx,
    preview_xlsx,
    save_bytes_as_file,
    stored_path,
)
from services.rag import touch_index_state
from util import now_stamp
from webutil import file_download, file_or_json, json_dict, respond

router = APIRouter()


@router.get("/api/files")
def list_files(request: Request):
    q = str(request.query_params.get("q") or "").strip()
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
    return respond({"success": True, "data": [file_to_dict(row) for row in rows]})


def store_uploaded_file(filename, data):
    record, error = save_bytes_as_file(filename, data)
    if error:
        audit("file.upload", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    audit(
        "file.upload",
        resource_id=record["id"],
        summary=f"{record['originalName']} ({record['kind']})",
    )
    return respond({"success": True, "message": "File uploaded", "data": record}, 201)


@router.post("/api/files")
def upload_file(incoming=Depends(file_or_json)):
    if incoming["kind"] == "file":
        return store_uploaded_file(incoming["filename"], incoming["data"])
    if incoming["kind"] == "missing":
        audit("file.upload", "failure", summary="no file uploaded")
        return respond({"success": False, "message": "No file was uploaded."}, 400)
    data = incoming["data"]
    filename = str(data.get("filename") or "")
    raw = str(data.get("content") or data.get("contentBase64") or "")
    if not raw:
        audit("file.upload", "failure", summary="no file uploaded")
        return respond({"success": False, "message": "No file was uploaded."}, 400)
    try:
        payload = base64.b64decode(raw, validate=False)
    except Exception:
        audit("file.upload", "failure", summary="invalid base64")
        return respond({"success": False, "message": "The file data is not valid base64."}, 400)
    if len(payload) > MAX_JSON_UPLOAD_MB * 1024 * 1024:
        audit("file.upload", "failure", summary=f"JSON upload exceeds {MAX_JSON_UPLOAD_MB} MB")
        return respond({
            "success": False,
            "message": f"JSON uploads are limited to {MAX_JSON_UPLOAD_MB} MB. Use a smaller file.",
        }, 400)
    return store_uploaded_file(filename, payload)


def _file_row_or_error(file_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM ToolkitFiles WHERE ID=?", (file_id,)).fetchone()
    if not row:
        return None, respond({"success": False, "message": "File not found"}, 404)
    path = stored_path(row["StoredName"])
    if not path.is_file():
        return None, respond({"success": False, "message": "File is missing on disk"}, 404)
    return (row, path), None


@router.get("/api/files/{file_id}/preview")
def preview_file(file_id: int):
    loaded, error = _file_row_or_error(file_id)
    if error:
        return error
    row, path = loaded
    kind = row["Kind"]
    try:
        if kind == "docx":
            preview = preview_docx(path)
        elif kind == "xlsx":
            preview = preview_xlsx(path)
        elif kind == "image":
            preview = {
                "kind": "image",
                "url": f"/api/files/{file_id}/content",
            }
        else:
            return respond({
                "success": False,
                "message": "Preview is not available for this file type.",
            }, 400)
    except Exception as error:
        return respond({"success": False, "message": f"Could not preview this file. {error}"}, 400)
    preview["file"] = file_to_dict(row)
    return respond({"success": True, "data": preview})


@router.get("/api/files/{file_id}/content")
def file_content(file_id: int):
    loaded, error = _file_row_or_error(file_id)
    if error:
        return error
    row, path = loaded
    if row["Kind"] != "image":
        return respond({
            "success": False,
            "message": "Inline preview is only available for pictures.",
        }, 400)
    return file_download(
        path,
        row["OriginalName"],
        media_type=image_mime_type(row["StoredName"]),
        inline=True,
    )


@router.get("/api/files/{file_id}")
def download_file(file_id: int):
    loaded, error = _file_row_or_error(file_id)
    if error:
        return error
    row, path = loaded
    return file_download(path, row["OriginalName"])


@router.patch("/api/files/{file_id}")
def rename_file(file_id: int, data: dict = Depends(json_dict)):
    name = Path(str(data.get("originalName") or data.get("name") or "")).name.strip()
    if not name:
        audit("file.rename", "failure", resource_id=file_id, summary="name required")
        return respond({"success": False, "message": "A file name is required."}, 400)
    kind, _suffix = file_kind_from_name(name)
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM ToolkitFiles WHERE ID=?", (file_id,)).fetchone()
        if not row:
            audit("file.rename", "failure", resource_id=file_id, summary="not found")
            return respond({"success": False, "message": "File not found"}, 404)
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
    audit("file.rename", resource_id=file_id, summary=name)
    return respond({"success": True, "message": "File renamed", "data": file_to_dict(updated)})


@router.delete("/api/files/{file_id}")
def delete_file(file_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM ToolkitFiles WHERE ID=?", (file_id,)).fetchone()
        if not row:
            audit("file.delete", "failure", resource_id=file_id, summary="not found")
            return respond({"success": False, "message": "File not found"}, 404)
        attached = conn.execute(
            "SELECT SopID FROM SopAttachments WHERE FileID=? LIMIT 1",
            (file_id,),
        ).fetchone()
        if attached:
            audit(
                "file.delete",
                "failure",
                resource_id=file_id,
                summary=f"{row['OriginalName']} attached to SOP",
            )
            return respond({
                "success": False,
                "message": "This file is attached to an SOP. Detach it first, then delete.",
            }, 409)
        conn.execute("DELETE FROM RagChunks WHERE SourceType='file' AND SourceID=?", (file_id,))
        conn.execute("DELETE FROM ToolkitFiles WHERE ID=?", (file_id,))
        touch_index_state(conn)
    path = stored_path(row["StoredName"])
    if path.is_file():
        path.unlink()
    audit("file.delete", resource_id=file_id, summary=row["OriginalName"])
    return respond({"success": True, "message": "File deleted"})
