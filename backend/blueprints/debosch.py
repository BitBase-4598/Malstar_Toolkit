from flask import Blueprint, jsonify, request

from logging_util import audit
from services.debosch import (
    create_debosch,
    delete_debosch,
    import_debosch_file,
    list_debosch,
    update_debosch,
)

bp = Blueprint("debosch", __name__)


def _label(row):
    return row.get("organizationCode") or row.get("fullName") or "DE-BOSCH"


@bp.get("/api/de-bosch")
def list_records():
    q = str(request.args.get("q") or "")
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 50, type=int)
    payload = list_debosch(q, page, page_size)
    return jsonify({"success": True, **payload})


@bp.post("/api/de-bosch")
def create_record():
    row, error = create_debosch(request.get_json(silent=True) or {})
    if error:
        audit("debosch.create", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    audit("debosch.create", summary=_label(row), resource_id=str(row["id"]))
    return jsonify({"success": True, "message": "DE-BOSCH created", "data": row}), 201


@bp.put("/api/de-bosch/<int:record_id>")
def update_record(record_id):
    row, error = update_debosch(record_id, request.get_json(silent=True) or {})
    if error:
        status = 404 if error == "Record not found" else 400
        audit("debosch.update", "failure", resource_id=record_id, summary=error)
        return jsonify({"success": False, "message": error}), status
    audit("debosch.update", summary=_label(row), resource_id=str(row["id"]))
    return jsonify({"success": True, "message": "DE-BOSCH updated", "data": row})


@bp.delete("/api/de-bosch/<int:record_id>")
def delete_record(record_id):
    row, error = delete_debosch(record_id)
    if error:
        audit("debosch.delete", "failure", resource_id=record_id, summary=error)
        return jsonify({"success": False, "message": error}), 404
    audit("debosch.delete", summary=_label(row), resource_id=str(row["id"]))
    return jsonify({"success": True, "message": "DE-BOSCH deleted", "data": row})


@bp.post("/api/de-bosch/import")
def import_records():
    if "file" not in request.files:
        audit("debosch.import", "failure", summary="no file uploaded")
        return jsonify({"success": False, "message": "No file was uploaded."}), 400
    file = request.files["file"]
    filename = file.filename or "Bosch-DE.xlsx"
    result, error = import_debosch_file(filename, file.read())
    if error:
        audit("debosch.import", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    audit("debosch.import", summary=f"file={result['filename']} rows={result['rowCount']}")
    noun = "organization" if result["rowCount"] == 1 else "organizations"
    return jsonify({
        "success": True,
        "message": f"Imported {result['rowCount']:,} DE-BOSCH {noun}",
        "data": result,
    })
