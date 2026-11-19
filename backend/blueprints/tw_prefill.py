from flask import Blueprint, jsonify, request

from logging_util import audit
from services.tw_prefill import import_tw_prefill_csv, suggest

bp = Blueprint("tw_prefill", __name__)


@bp.get("/api/tw-prefill/suggest")
def suggest_records():
    payload = suggest(
        shipper=request.args.get("shipper") or "",
        shipper_name=request.args.get("shipperName") or "",
        consignee=request.args.get("consignee") or "",
        consignee_name=request.args.get("consigneeName") or "",
        origin=request.args.get("origin") or "",
        dest=request.args.get("dest") or "",
    )
    return jsonify({"success": True, **payload})


@bp.post("/api/tw-prefill/import")
def import_records():
    if "file" not in request.files:
        audit("twprefill.import", "failure", summary="no file uploaded")
        return jsonify({"success": False, "message": "No file was uploaded."}), 400
    file = request.files["file"]
    filename = file.filename or "tw-prefill.csv"
    result, error = import_tw_prefill_csv(filename, file.read())
    if error:
        audit("twprefill.import", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    count = result["rowCount"]
    noun = "shipment" if count == 1 else "shipments"
    audit("twprefill.import", summary=f"file={result['filename']} rows={count}")
    return jsonify({
        "success": True,
        "message": f"Imported {count:,} {noun}",
        "data": result,
    })
