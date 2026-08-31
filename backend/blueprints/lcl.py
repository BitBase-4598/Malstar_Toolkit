from flask import Blueprint, jsonify, request

from logging_util import audit
from services.lcl import build_dashboard, build_map, build_summary, import_lcl_workbook, list_filter_options

bp = Blueprint("lcl", __name__)


@bp.get("/api/lcl/filters")
def lcl_filters():
    return jsonify({"success": True, "data": list_filter_options()})


@bp.get("/api/lcl/dashboard")
def lcl_dashboard():
    return jsonify({"success": True, "data": build_dashboard(request.args)})


@bp.get("/api/lcl/summary")
def lcl_summary():
    return jsonify({"success": True, "data": build_summary(request.args)})


@bp.get("/api/lcl/map")
def lcl_map():
    return jsonify({"success": True, "data": build_map(request.args)})


@bp.post("/api/lcl/import")
def lcl_import():
    if "file" not in request.files:
        audit("lcl.import", "failure", summary="no file uploaded")
        return jsonify({"success": False, "message": "No file was uploaded."}), 400
    file = request.files["file"]
    filename = file.filename or "lcl.xlsx"
    result, error = import_lcl_workbook(filename, file.read())
    if error:
        audit("lcl.import", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    audit(
        "lcl.import",
        summary=f"{result['filename']} export={result['exportCount']} import={result['importCount']}",
    )
    return jsonify({
        "success": True,
        "message": f"Imported {result['total']:,} LCL shipments",
        "data": result,
    })
