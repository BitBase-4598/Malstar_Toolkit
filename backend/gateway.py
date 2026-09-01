"""Public reverse proxy on port 80.

Tencent Cloud security groups on this CVM allow 80 but not 8080.
This gateway keeps Time Motion Tracker Pro at / and exposes Customer Remarks at /remarks/.
"""

import json
import os
import socket
import urllib.error
import urllib.request

from flask import Flask, Response, request
from waitress import serve

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


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024
app.config["MAX_FORM_MEMORY_SIZE"] = 512 * 1024 * 1024


@app.before_request
def route_remarks_first():
    path = request.path
    if path == "/remarks" or path.startswith("/remarks/"):
        subpath = path[len("/remarks"):].lstrip("/")
        return _forward(REMARKS_UPSTREAM, subpath)


def _forward_timeout(subpath, method):
    if method in {"POST", "PUT", "PATCH"}:
        return WRITE_TIMEOUT
    path = "/" + str(subpath or "").lstrip("/")
    if any(path.startswith(prefix) for prefix in HEAVY_GET_PREFIXES):
        return GET_TIMEOUT
    return GET_TIMEOUT


def _json_error(message, status):
    payload = json.dumps({"success": False, "message": message})
    return Response(payload, status, [("Content-Type", "application/json")])


def _forward(target_base, subpath=""):
    url = target_base.rstrip("/") + "/" + subpath.lstrip("/")
    query = request.query_string.decode()
    if query:
        url = f"{url}?{query}"
    headers = {
        key: value
        for key, value in request.headers
        if key.lower() not in SKIP_REQ_HEADERS
    }
    body = request.get_data()
    req = urllib.request.Request(
        url,
        data=body if body else None,
        headers=headers,
        method=request.method,
    )
    timeout = _forward_timeout(subpath, request.method)
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as error:
        out_headers = [
            (key, value)
            for key, value in error.headers.items()
            if key.lower() not in SKIP_RES_HEADERS
        ]

        def error_chunks():
            try:
                while True:
                    chunk = error.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
            finally:
                error.close()

        return Response(error_chunks(), error.code, out_headers)
    except TimeoutError:
        return _json_error("The request timed out.", 504)
    except socket.timeout:
        return _json_error("The request timed out.", 504)
    except urllib.error.URLError as error:
        reason = error.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return _json_error("The request timed out.", 504)
        return _json_error("The upstream service is unavailable.", 502)

    out_headers = [
        (key, value)
        for key, value in response.headers.items()
        if key.lower() not in SKIP_RES_HEADERS
    ]

    def body_chunks():
        try:
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        finally:
            response.close()

    return Response(body_chunks(), response.status, out_headers)


@app.route("/remarks", methods=["GET", "HEAD"])
def remarks_root():
    return _forward(REMARKS_UPSTREAM)


@app.route("/remarks/<path:asset_path>", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def remarks_proxy(asset_path):
    return _forward(REMARKS_UPSTREAM, asset_path)


@app.route("/", defaults={"asset_path": ""}, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@app.route("/<path:asset_path>", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def timer_proxy(asset_path):
    return _forward(TIMER_UPSTREAM, asset_path)


if __name__ == "__main__":
    print(f"Public gateway on http://{LISTEN_HOST}:{LISTEN_PORT}")
    print(f"  /remarks -> {REMARKS_UPSTREAM}")
    print(f"  /        -> {TIMER_UPSTREAM}")
    serve(app, host=LISTEN_HOST, port=LISTEN_PORT, threads=8, channel_timeout=900)
