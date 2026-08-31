from flask import Blueprint, jsonify, request

from logging_util import audit
from services.gca import (
    build_summary,
    import_gca_workbook,
    list_bookings,
    list_feedback,
    parse_date_arg,
)

bp = Blueprint("gca", __name__)


def _dates():
    date_from, error = parse_date_arg(request.args.get("dateFrom"))
    if error:
        return None, None, error
    date_to, error = parse_date_arg(request.args.get("dateTo"))
    if error:
        return None, None, error
    return date_from, date_to, None


@bp.get("/api/gca/summary")
def gca_summary():
    date_from, date_to, error = _dates()
    if error:
        return jsonify({"success": False, "message": error}), 400
    data = build_summary(date_from, date_to, request.args.get("lane"))
    return jsonify({"success": True, "data": data})


@bp.get("/api/gca/bookings")
def gca_bookings():
    date_from, date_to, error = _dates()
    if error:
        return jsonify({"success": False, "message": error}), 400
    payload = list_bookings(
        date_from,
        date_to,
        request.args.get("lane"),
        request.args.get("q") or "",
        request.args.get("page", 1, type=int),
        request.args.get("pageSize", 50, type=int),
    )
    return jsonify({"success": True, **payload})


@bp.get("/api/gca/feedback")
def gca_feedback():
    date_from, date_to, error = _dates()
    if error:
        return jsonify({"success": False, "message": error}), 400
    payload = list_feedback(
        date_from,
        date_to,
        request.args.get("lane"),
        request.args.get("q") or "",
        request.args.get("page", 1, type=int),
        request.args.get("pageSize", 50, type=int),
    )
    return jsonify({"success": True, **payload})


@bp.post("/api/gca/import")
def gca_import():
    if "file" not in request.files:
        audit("gca.import", "failure", summary="no file uploaded")
        return jsonify({"success": False, "message": "No file was uploaded."}), 400
    file = request.files["file"]
    filename = file.filename or "gca.xlsx"
    result, error = import_gca_workbook(filename, file.read())
    if error:
        audit("gca.import", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    audit(
        "gca.import",
        summary=f"file={result['filename']} bookings={result['bookingCount']} feedback={result['feedbackCount']}",
    )
    return jsonify({
        "success": True,
        "message": (
            f"Imported {result['bookingCount']} booking"
            + ("" if result["bookingCount"] == 1 else "s")
            + f" and {result['feedbackCount']} feedback row"
            + ("" if result["feedbackCount"] == 1 else "s")
        ),
        "data": result,
    })
