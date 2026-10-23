"""Public reverse proxy on port 80.

Tencent Cloud security groups on this CVM allow 80 but not 8080.
This gateway keeps Time Motion Tracker Pro at / and exposes Customer Remarks at /remarks/.
"""

import os
import socket
import urllib.error
import urllib.request

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

TIMER_UPSTREAM = os.environ.get("TIMER_UPSTREAM", "http://127.0.0.1:8081")
REMARKS_UPSTREAM = os.environ.get("REMARKS_UPSTREAM", "http://127.0.0.1:8080")
LISTEN_HOST = os.environ.get("GATEWAY_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("GATEWAY_PORT", "80"))
SKIP_REQ_HEADERS = {"host", "content-length", "connection", "transfer-encoding"}
SKIP_RES_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-encoding",
    "content-length",
}
CHUNK_SIZE = 64 * 1024
GET_TIMEOUT = 300
WRITE_TIMEOUT = 900
HEAVY_GET_PREFIXES = ("/api/lcl", "/api/unlocode")


def _forward_timeout(subpath, method):
    if method in {"POST", "PUT", "PATCH"}:
        return WRITE_TIMEOUT
    path = "/" + str(subpath or "").lstrip("/")
    if any(path.startswith(prefix) for prefix in HEAVY_GET_PREFIXES):
        return GET_TIMEOUT
    return GET_TIMEOUT


def _json_error(message, status):
    return JSONResponse({"success": False, "message": message}, status_code=status)


def _open_upstream(url, headers, body, method, timeout):
    req = urllib.request.Request(
        url,
        data=body if body else None,
        headers=headers,
        method=method,
    )
    return urllib.request.urlopen(req, timeout=timeout)


async def _forward(request, target_base, subpath=""):
    url = target_base.rstrip("/") + "/" + subpath.lstrip("/")
    query = request.url.query
    if query:
        url = f"{url}?{query}"
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in SKIP_REQ_HEADERS
    }
    body = await request.body()
    timeout = _forward_timeout(subpath, request.method)
    try:
        response = _open_upstream(url, headers, body, request.method, timeout)
    except urllib.error.HTTPError as error:
        out_headers = {
            key: value
            for key, value in error.headers.items()
            if key.lower() not in SKIP_RES_HEADERS
        }

        def error_chunks():
            try:
                while True:
                    chunk = error.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
            finally:
                error.close()

        return StreamingResponse(error_chunks(), status_code=error.code, headers=out_headers)
    except TimeoutError:
        return _json_error("The request timed out.", 504)
    except socket.timeout:
        return _json_error("The request timed out.", 504)
    except urllib.error.URLError as error:
        reason = error.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return _json_error("The request timed out.", 504)
        return _json_error("The upstream service is unavailable.", 502)

    out_headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in SKIP_RES_HEADERS
    }

    def body_chunks():
        try:
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        finally:
            response.close()

    return StreamingResponse(body_chunks(), status_code=response.status, headers=out_headers)


async def dispatch(request):
    path = request.url.path
    if path == "/remarks" or path.startswith("/remarks/"):
        subpath = path[len("/remarks"):].lstrip("/")
        return await _forward(request, REMARKS_UPSTREAM, subpath)
    return await _forward(request, TIMER_UPSTREAM, path.lstrip("/"))


app = Starlette(routes=[Route("/{path:path}", dispatch, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])])
# Starlette Route path does not match "/" with {path:path} in every version. Mount both.
app.router.routes.insert(0, Route("/", dispatch, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]))


if __name__ == "__main__":
    print(f"Public gateway on http://{LISTEN_HOST}:{LISTEN_PORT}")
    print(f"  /remarks -> {REMARKS_UPSTREAM}")
    print(f"  /        -> {TIMER_UPSTREAM}")
    uvicorn.run(app, host=LISTEN_HOST, port=LISTEN_PORT, timeout_keep_alive=900)
