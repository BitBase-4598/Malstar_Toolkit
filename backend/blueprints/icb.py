from flask import Blueprint, jsonify, request

from logging_util import audit
from services.icb import import_icb_csv, list_icb_stations

bp = Blueprint("icb", __name__)


@bp.get("/api/icb")
def list_icb():
    q = str(request.args.get("q") or "")
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 100, type=int)
    payload = list_icb_stations(q, page, page_size)
    return jsonify({"success": True, **payload})


@bp.post("/api/icb/import")
def import_icb():
    if "file" not in request.files:
        audit("icb.import", "failure", summary="no file uploaded")
        return jsonify({"success": False, "message": "No file was uploaded."}), 400
    file = request.files["file"]
    filename = file.filename or "icb.csv"
    result, error = import_icb_csv(filename, file.read())
    if error:
        audit("icb.import", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    audit("icb.import", summary=f"file={result['filename']} rows={result['rowCount']}")
    return jsonify({
        "success": True,
        "message": f"Imported {result['rowCount']} ICB station" + ("" if result["rowCount"] == 1 else "s"),
        "data": result,
    })
