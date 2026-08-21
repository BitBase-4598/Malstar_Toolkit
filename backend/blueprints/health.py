from flask import Blueprint, jsonify

bp = Blueprint("health", __name__)


@bp.get("/api/health")
def health():
    return jsonify({"success": True, "message": "MALSTAR_Toolkit API is running"})
