import base64

from flask import Blueprint, jsonify, request

from config import MAX_JSON_UPLOAD_MB
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


def _json_upload():
    data = request.get_json(silent=True) or {}
    csv_text = data.get("csv")
    filename = str(data.get("filename") or "tw-prefill.csv")
    if isinstance(csv_text, str) and csv_text.strip():
        payload = csv_text.encode("utf-8")
        if len(payload) > 8 * 1024 * 1024:
            return None, None, "Each upload part is limited to 8 MB."
        return filename, payload, None
    raw = str(data.get("content") or data.get("contentBase64") or "")
    if not raw:
        return None, None, "No file was uploaded."
    try:
        payload = base64.b64decode(raw, validate=False)
    except Exception:
        return None, None, "The file data is not valid base64."
    if len(payload) > MAX_JSON_UPLOAD_MB * 1024 * 1024:
        return None, None, f"JSON uploads are limited to {MAX_JSON_UPLOAD_MB} MB. Use a smaller file."
    return filename, payload, None


@bp.post("/api/tw-prefill/import")
def import_records():
    if "file" in request.files:
        file = request.files["file"]
        filename = file.filename or "tw-prefill.csv"
        raw = file.read()
    else:
        filename, raw, error = _json_upload()
        if error:
            audit("twprefill.import", "failure", summary=error)
            return jsonify({"success": False, "message": error}), 400
    result, error = import_tw_prefill_csv(filename, raw)
    if error:
        audit("twprefill.import", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    added = result["added"]
    skipped = result["skipped"]
    noun = "shipment" if added == 1 else "shipments"
    audit(
        "twprefill.import",
        summary=f"file={result['filename']} added={added} skipped={skipped} total={result['rowCount']}",
    )
    return jsonify({
        "success": True,
        "message": f"Added {added:,} {noun}, skipped {skipped:,} duplicates",
        "data": result,
    })
