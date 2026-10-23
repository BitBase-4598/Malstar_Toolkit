import os
import threading
import uuid

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse

from config import CORS_ORIGINS, LCL_MAX_UPLOAD_MB, MAX_UPLOAD_MB, STATIC_DIR
from db import migrate
from logging_util import APP_LOGGER, audit, bind_http_context, reset_http_context
from webutil import attach_test_client, respond

_migrate_lock = threading.Lock()
_migrated = False


def ensure_migrated():
    global _migrated
    if _migrated:
        return
    with _migrate_lock:
        if not _migrated:
            migrate()
            _migrated = True


def _static_response(asset_path):
    root = STATIC_DIR.resolve()
    if asset_path.startswith("api/") or asset_path == "api":
        return respond({"success": False, "message": "Not found"}, 404)
    target = (STATIC_DIR / asset_path).resolve()
    if root != target and root not in target.parents:
        return respond({"success": False, "message": "Not found"}, 404)
    if target.is_file():
        return FileResponse(target)
    index = root / "index.html"
    if index.is_file():
        return FileResponse(index)
    return respond({"success": False, "message": "Not found"}, 404)


def create_app():
    app = FastAPI(title="MALSTAR Toolkit")
    upload_cap = max(MAX_UPLOAD_MB, LCL_MAX_UPLOAD_MB) * 1024 * 1024
    limit_mb = max(MAX_UPLOAD_MB, LCL_MAX_UPLOAD_MB)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        incoming = str(request.headers.get("x-request-id") or "").strip()[:80]
        request_id = incoming or str(uuid.uuid4())
        client_ip = request.client.host if request.client else ""
        user_agent = str(request.headers.get("user-agent") or "")
        tokens = bind_http_context(request_id, client_ip, user_agent)
        try:
            length = request.headers.get("content-length")
            if length:
                try:
                    too_big = int(length) > upload_cap
                except ValueError:
                    too_big = False
                if too_big:
                    response = respond({
                        "success": False,
                        "message": f"Upload exceeds the {limit_mb} MB limit.",
                    }, 413)
                    response.headers["X-Request-ID"] = request_id
                    return response
            if request.url.path != "/api/health":
                ensure_migrated()
            try:
                response = await call_next(request)
            except RequestValidationError:
                raise
            except HTTPException as error:
                detail = error.detail if isinstance(error.detail, dict) else {"detail": error.detail}
                response = JSONResponse(detail, status_code=error.status_code)
            except Exception as error:
                if request.url.path.startswith("/api/"):
                    APP_LOGGER.exception("unhandled api exception")
                    audit(
                        "server.exception",
                        outcome="exception",
                        summary=f"{type(error).__name__}: {error}",
                        extra={"path": request.url.path, "method": request.method},
                        exc_info=True,
                    )
                    response = respond({
                        "success": False,
                        "message": "The server could not complete this request.",
                    }, 500)
                else:
                    raise
        finally:
            reset_http_context(tokens)
        response.headers["X-Request-ID"] = request_id
        return response

    if CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=CORS_ORIGINS,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    from blueprints.ask import router as ask_router
    from blueprints.cases import router as cases_router
    from blueprints.dashboard import router as dashboard_router
    from blueprints.debosch import router as debosch_router
    from blueprints.delcl import router as delcl_router
    from blueprints.files import router as files_router
    from blueprints.gca import router as gca_router
    from blueprints.health import router as health_router
    from blueprints.icb import router as icb_router
    from blueprints.lcl import router as lcl_router
    from blueprints.leave import router as leave_router
    from blueprints.logs import router as logs_router
    from blueprints.remarks import router as remarks_router
    from blueprints.sops import router as sops_router
    from blueprints.unloco import router as unloco_router

    for feature in (
        health_router,
        logs_router,
        files_router,
        sops_router,
        cases_router,
        ask_router,
        leave_router,
        lcl_router,
        dashboard_router,
        icb_router,
        unloco_router,
        delcl_router,
        debosch_router,
        gca_router,
        remarks_router,
    ):
        app.include_router(feature)

    @app.get("/")
    def index():
        index_file = STATIC_DIR / "index.html"
        if not index_file.is_file():
            return respond({
                "success": True,
                "message": "MALSTAR_Toolkit API is running. Frontend build not found.",
            })
        return FileResponse(index_file)

    @app.get("/lcl")
    @app.get("/lcl/")
    @app.get("/lcl.html")
    def lcl_page():
        page = STATIC_DIR / "lcl.html"
        if page.is_file():
            return FileResponse(page)
        return respond({"success": False, "message": "Not found"}, 404)

    @app.get("/{asset_path:path}")
    def spa_or_static(asset_path: str):
        return _static_response(asset_path)

    return attach_test_client(app)


app = create_app()


def _warm_lcl_cache():
    try:
        from services.lcl import build_dashboard
        build_dashboard({})
    except Exception:
        pass


def _warm_unloco():
    try:
        ensure_migrated()
        from services.unloco import ensure_unloco_loaded
        ensure_unloco_loaded()
    except Exception:
        pass


def _warm_delcl():
    try:
        ensure_migrated()
        from services.delcl import ensure_delcl_loaded
        ensure_delcl_loaded()
    except Exception:
        pass


def _warm_debosch():
    try:
        ensure_migrated()
        from services.debosch import ensure_debosch_loaded
        ensure_debosch_loaded()
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn

    threading.Thread(target=_warm_lcl_cache, daemon=True).start()
    threading.Thread(target=_warm_unloco, daemon=True).start()
    threading.Thread(target=_warm_delcl, daemon=True).start()
    threading.Thread(target=_warm_debosch, daemon=True).start()
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", os.environ.get("FLASK_PORT", "5000")))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    print(f"MALSTAR_Toolkit on http://{host}:{port} (uvicorn)")
    uvicorn.run(app, host=host, port=port, log_level="debug" if debug else "info")
