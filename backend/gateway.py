"""Public reverse proxy on port 80.

Tencent Cloud security groups on this CVM allow 80 but not 8080.
This gateway keeps Time Motion Tracker Pro at / and exposes Customer Remarks at /remarks/.
"""

import os
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

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024
app.config["MAX_FORM_MEMORY_SIZE"] = 512 * 1024 * 1024


@app.before_request
def route_remarks_first():
    path = request.path
    if path == "/remarks" or path.startswith("/remarks/"):
        subpath = path[len("/remarks"):].lstrip("/")
        return _forward(REMARKS_UPSTREAM, subpath)


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
    timeout = 900 if request.method in {"POST", "PUT", "PATCH"} else 120
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            out_headers = [
                (key, value)
                for key, value in response.headers.items()
                if key.lower() not in SKIP_RES_HEADERS
            ]
            return Response(response.read(), response.status, out_headers)
    except urllib.error.HTTPError as error:
        out_headers = [
            (key, value)
            for key, value in error.headers.items()
            if key.lower() not in SKIP_RES_HEADERS
        ]
        return Response(error.read(), error.code, out_headers)


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
