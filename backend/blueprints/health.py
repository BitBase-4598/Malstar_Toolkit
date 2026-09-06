from flask import Blueprint, jsonify

from db_engine import ping

bp = Blueprint("health", __name__)


@bp.get("/api/health")
def health():
    try:
        ping()
    except Exception:
        return jsonify({
            "success": False,
            "message": "MALSTAR_Toolkit API cannot reach the database.",
        }), 503
    return jsonify({"success": True, "message": "MALSTAR_Toolkit API is running"})
