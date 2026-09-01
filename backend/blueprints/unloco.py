from flask import Blueprint, jsonify, request

from logging_util import audit
from services.unloco import create_unlocode, import_unloco_csv, list_unlocodes

bp = Blueprint("unloco", __name__)


@bp.get("/api/unlocode")
def list_unloco():
    q = str(request.args.get("q") or "")
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 50, type=int)
    payload = list_unlocodes(q, page, page_size)
    return jsonify({"success": True, **payload})


@bp.post("/api/unlocode")
def create_unloco():
    row, error = create_unlocode(request.get_json(silent=True) or {})
    if error:
        audit("unloco.create", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    audit(
        "unloco.create",
        summary=f"{row['unCode'] or row['portName']} / {row['countryCode']}",
        resource_id=str(row["id"]),
    )
    return jsonify({"success": True, "message": "UNLOCODE created", "data": row}), 201


@bp.post("/api/unlocode/import")
def import_unloco():
    if "file" not in request.files:
        audit("unloco.import", "failure", summary="no file uploaded")
        return jsonify({"success": False, "message": "No file was uploaded."}), 400
    file = request.files["file"]
    filename = file.filename or "UNLOCODE.csv"
    result, error = import_unloco_csv(filename, file.read())
    if error:
        audit("unloco.import", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    audit("unloco.import", summary=f"file={result['filename']} rows={result['rowCount']}")
    return jsonify({
        "success": True,
        "message": f"Imported {result['rowCount']:,} UNLOCODE" + ("" if result["rowCount"] == 1 else "s"),
        "data": result,
    })
