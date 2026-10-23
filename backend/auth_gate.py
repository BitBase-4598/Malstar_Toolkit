"""Shared-password HTTP Basic Auth for CVM deployments without a login system."""

from __future__ import annotations

import base64
import hmac
import os

from flask import Request, Response, jsonify

REALM = "MALSTAR Toolkit"
HEALTH_PATH = "/api/health"


def basic_auth_enabled() -> bool:
    return bool((os.environ.get("TOOLKIT_BASIC_PASSWORD") or "").strip())


def expected_credentials() -> tuple[str, str]:
    user = (os.environ.get("TOOLKIT_BASIC_USER") or "malstar").strip() or "malstar"
    password = (os.environ.get("TOOLKIT_BASIC_PASSWORD") or "").strip()
    return user, password


def _unauthorized() -> Response:
    response = jsonify({
        "success": False,
        "message": "Authentication required.",
    })
    response.status_code = 401
    response.headers["WWW-Authenticate"] = f'Basic realm="{REALM}"'
    return response


def _parse_basic(header: str | None) -> tuple[str, str] | None:
    if not header:
        return None
    scheme, _, rest = header.partition(" ")
    if scheme.lower() != "basic" or not rest.strip():
        return None
    try:
        decoded = base64.b64decode(rest.strip(), validate=True).decode("utf-8")
    except Exception:
        return None
    if ":" not in decoded:
        return None
    username, _, password = decoded.partition(":")
    return username, password


def check_basic_auth(request: Request) -> Response | None:
    """Return a 401 response when auth is enabled and credentials are missing/wrong."""
    if request.path == HEALTH_PATH:
        return None
    if not basic_auth_enabled():
        return None
    expected_user, expected_password = expected_credentials()
    parsed = _parse_basic(request.headers.get("Authorization"))
    if parsed is None:
        return _unauthorized()
    username, password = parsed
    user_ok = hmac.compare_digest(username, expected_user)
    pass_ok = hmac.compare_digest(password, expected_password)
    if not (user_ok and pass_ok):
        return _unauthorized()
    return None
