import os

from flask import Flask, abort, g, jsonify, send_from_directory
from flask_cors import CORS

from config import CORS_ORIGINS, MAX_UPLOAD_MB, STATIC_DIR
from db import migrate


def create_app():
    migrate()
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    app.config["MAX_FORM_MEMORY_SIZE"] = MAX_UPLOAD_MB * 1024 * 1024
    app.config["MAX_FORM_PARTS"] = 10000
    if CORS_ORIGINS:
        CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS}})

    from blueprints.ask import bp as ask_bp
    from blueprints.dashboard import bp as dashboard_bp
    from blueprints.files import bp as files_bp
    from blueprints.health import bp as health_bp
    from blueprints.leave import bp as leave_bp
    from blueprints.logs import bp as logs_bp
    from blueprints.remarks import bp as remarks_bp
    from blueprints.sops import bp as sops_bp
    from logging_util import APP_LOGGER, assign_request_id, audit

    app.register_blueprint(health_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(sops_bp)
    app.register_blueprint(ask_bp)
    app.register_blueprint(leave_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(remarks_bp)

    @app.before_request
    def bind_request_id():
        assign_request_id()

    @app.after_request
    def echo_request_id(response):
        request_id = getattr(g, "request_id", "")
        if request_id:
            response.headers["X-Request-ID"] = request_id
        return response

    @app.errorhandler(413)
    def too_large(_):
        return jsonify({
            "success": False,
            "message": f"Upload exceeds the {MAX_UPLOAD_MB} MB limit.",
        }), 413

    @app.errorhandler(Exception)
    def unhandled_error(error):
        from flask import request
        from werkzeug.exceptions import HTTPException

        if isinstance(error, HTTPException):
            return error
        if request.path.startswith("/api/"):
            APP_LOGGER.exception("unhandled api exception")
            audit(
                "server.exception",
                outcome="exception",
                summary=f"{type(error).__name__}: {error}",
                extra={"path": request.path, "method": request.method},
                exc_info=True,
            )
            return jsonify({
                "success": False,
                "message": "The server could not complete this request.",
            }), 500
        raise error

    @app.get("/")
    def index():
        if not (STATIC_DIR / "index.html").is_file():
            return jsonify({
                "success": True,
                "message": "MALSTAR_Toolkit API is running. Frontend build not found.",
            })
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/<path:asset_path>")
    def spa_or_static(asset_path):
        if asset_path.startswith("api/"):
            abort(404)
        target = STATIC_DIR / asset_path
        if target.is_file():
            return send_from_directory(STATIC_DIR, asset_path)
        if (STATIC_DIR / "index.html").is_file():
            return send_from_directory(STATIC_DIR, "index.html")
        abort(404)

    return app


app = create_app()


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", os.environ.get("FLASK_PORT", "5000")))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
