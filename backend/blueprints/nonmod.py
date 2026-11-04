from flask import Blueprint, jsonify, request

from logging_util import audit
from services.nonmod import (
    field_ranking,
    import_nonmod_workbook,
    latest_snapshot,
    list_rows,
    parse_report_date,
)

bp = Blueprint("nonmod", __name__)


def _page_arg(name, default):
    raw = request.args.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


@bp.post("/api/non-mod/upload")
def upload_non_mod():
    if "file" not in request.files:
        audit("nonmod.upload", "failure", summary="no file uploaded")
        return jsonify({"success": False, "message": "No file was uploaded."}), 400
    uploaded = request.files["file"]
    filename = uploaded.filename or ""
    report_date = str(request.form.get("reportDate") or request.args.get("reportDate") or "")
    result, error = import_nonmod_workbook(filename, uploaded.read(), report_date)
    if error:
        audit("nonmod.upload", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    data = result["data"]
    audit(
        "nonmod.upload",
        resource_id=data["meta"]["reportDate"],
        summary=(
            f"file={data['meta']['filename']} reportDate={data['meta']['reportDate']} "
            f"rows={data['selectedBookings']} matched={data['matchedBookings']}"
        ),
    )
    return jsonify({"success": True, "message": result["message"], "data": data})


@bp.get("/api/non-mod/latest")
def non_mod_latest():
    return jsonify({"success": True, "data": latest_snapshot()})


@bp.get("/api/non-mod/rows")
def non_mod_rows():
    report_date = str(request.args.get("reportDate") or "")
    parsed, error = parse_report_date(report_date)
    if error:
        return jsonify({"success": False, "message": error}), 400
    payload, error = list_rows(parsed, _page_arg("page", 1), _page_arg("pageSize", 50))
    if error:
        status = 404 if error.startswith("No Non-Mod snapshot") else 400
        return jsonify({"success": False, "message": error}), status
    return jsonify({"success": True, **payload})


@bp.get("/api/non-mod/field-ranking")
def non_mod_field_ranking():
    report_date = str(request.args.get("reportDate") or "")
    parsed, error = parse_report_date(report_date)
    if error:
        return jsonify({"success": False, "message": error}), 400
    data, error = field_ranking(parsed)
    if error:
        status = 404 if error.startswith("No Non-Mod snapshot") else 400
        return jsonify({"success": False, "message": error}), status
    return jsonify({"success": True, "data": data})
