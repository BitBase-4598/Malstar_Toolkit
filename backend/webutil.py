import json

from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response


def respond(payload, status=200):
    return JSONResponse(payload, status_code=status)


def query_int(request: Request, name: str, default: int) -> int:
    raw = request.query_params.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


async def json_dict(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


async def read_upload(request: Request):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        return None
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        return None
    return upload.filename or "", await upload.read()


async def file_or_json(request: Request):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            return {"kind": "missing"}
        return {
            "kind": "file",
            "filename": upload.filename or "",
            "data": await upload.read(),
        }
    return {"kind": "json", "data": await json_dict(request)}


def attachment(content, filename, media_type, inline=False):
    if hasattr(content, "getvalue"):
        content = content.getvalue()
    disposition = "inline" if inline else "attachment"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


def file_download(path, filename, media_type=None, inline=False):
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline" if inline else "attachment",
    )


class ApiResponse:
    def __init__(self, response):
        self._response = response
        self.status_code = response.status_code
        self.headers = response.headers
        self.data = response.content

    @property
    def mimetype(self):
        raw = self.headers.get("content-type") or ""
        return raw.split(";", 1)[0].strip()

    def get_json(self, silent=False):
        if not self._response.content:
            return None
        try:
            return self._response.json()
        except Exception:
            if silent:
                return None
            raise

    def get_data(self, as_text=False):
        if as_text:
            return self._response.text
        return self._response.content


class ApiClient:
    def __init__(self, app):
        self._client = TestClient(app, raise_server_exceptions=False)

    def request(self, method, path, json=None, data=None, content_type=None, headers=None):
        kwargs = {}
        if headers:
            kwargs["headers"] = dict(headers)
        if json is not None:
            kwargs["json"] = json
        elif isinstance(data, dict) and any(isinstance(value, tuple) for value in data.values()):
            files = {}
            for key, value in data.items():
                handle, filename = value[0], value[1]
                payload = handle.getvalue() if hasattr(handle, "getvalue") else handle.read()
                files[key] = (filename, payload)
            kwargs["files"] = files
        elif data is not None:
            kwargs["data"] = data
            if content_type:
                kwargs.setdefault("headers", {})["content-type"] = content_type
        response = self._client.request(method, path, **kwargs)
        return ApiResponse(response)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)

    def patch(self, path, **kwargs):
        return self.request("PATCH", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)


def attach_test_client(app):
    app.test_client = lambda: ApiClient(app)
    return app
