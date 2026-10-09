from flask import Blueprint, jsonify, request

from logging_util import audit
from services.delcl import (
    create_delcl,
    delete_delcl,
    import_delcl_file,
    list_delcl,
    update_delcl,
)

bp = Blueprint("delcl", __name__)


def _label(row):
    return row.get("orgaCode") or row.get("consigneeName") or row.get("consignee") or "DE-LCL"


@bp.get("/api/de-lcl")
def list_records():
    q = str(request.args.get("q") or "")
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 50, type=int)
    payload = list_delcl(q, page, page_size)
    return jsonify({"success": True, **payload})


@bp.post("/api/de-lcl")
def create_record():
    row, error = create_delcl(request.get_json(silent=True) or {})
    if error:
        audit("delcl.create", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    audit("delcl.create", summary=_label(row), resource_id=str(row["id"]))
    return jsonify({"success": True, "message": "DE-LCL created", "data": row}), 201


@bp.put("/api/de-lcl/<int:record_id>")
def update_record(record_id):
    row, error = update_delcl(record_id, request.get_json(silent=True) or {})
    if error:
        status = 404 if error == "Record not found" else 400
        audit("delcl.update", "failure", resource_id=record_id, summary=error)
        return jsonify({"success": False, "message": error}), status
    audit("delcl.update", summary=_label(row), resource_id=str(row["id"]))
    return jsonify({"success": True, "message": "DE-LCL updated", "data": row})


@bp.delete("/api/de-lcl/<int:record_id>")
def delete_record(record_id):
    row, error = delete_delcl(record_id)
    if error:
        audit("delcl.delete", "failure", resource_id=record_id, summary=error)
        return jsonify({"success": False, "message": error}), 404
    audit("delcl.delete", summary=_label(row), resource_id=str(row["id"]))
    return jsonify({"success": True, "message": "DE-LCL deleted", "data": row})


@bp.post("/api/de-lcl/import")
def import_records():
    if "file" not in request.files:
        audit("delcl.import", "failure", summary="no file uploaded")
        return jsonify({"success": False, "message": "No file was uploaded."}), 400
    file = request.files["file"]
    filename = file.filename or "DE-LCL.xlsx"
    result, error = import_delcl_file(filename, file.read())
    if error:
        audit("delcl.import", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    audit("delcl.import", summary=f"file={result['filename']} rows={result['rowCount']}")
    return jsonify({
        "success": True,
        "message": f"Imported {result['rowCount']:,} DE-LCL" + ("" if result["rowCount"] == 1 else "s"),
        "data": result,
    })
