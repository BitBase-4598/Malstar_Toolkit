"""Entra sign-in identity and viewer/editor/admin checks.

Azure App Service Authentication forwards the signed-in user on
X-MS-CLIENT-PRINCIPAL, X-MS-CLIENT-PRINCIPAL-NAME, and
X-MS-CLIENT-PRINCIPAL-ID. App roles Malstar.Viewer, Malstar.Editor, and
Malstar.Admin map onto the toolkit roles. Without those headers the process
uses MALSTAR_DEFAULT_ROLE so a local or CVM process keeps working. Set
MALSTAR_AUTH_REQUIRED=1 to refuse anonymous API calls.
"""

import base64
import json
import os

from flask import g, has_request_context, jsonify, request

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ROLE_RANK = {"viewer": 1, "editor": 2, "admin": 3}
OPEN_PATHS = {"/api/health"}


def auth_required():
    return os.environ.get("MALSTAR_AUTH_REQUIRED", "").strip().lower() in ("1", "true", "yes")


def default_role():
    role = _normalize_role(os.environ.get("MALSTAR_DEFAULT_ROLE", "editor"))
    return role or "editor"


def _normalize_role(value):
    text = str(value or "").strip()
    if not text:
        return ""
    tail = text.split(".")[-1].casefold()
    if tail in ROLE_RANK:
        return tail
    folded = text.casefold()
    return folded if folded in ROLE_RANK else ""


def _decode_principal(value):
    raw = str(value or "").strip()
    if not raw:
        return {}
    padding = "=" * (-len(raw) % 4)
    try:
        decoded = base64.urlsafe_b64decode(raw + padding)
        data = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _claims(principal):
    claims = principal.get("claims") or []
    if not isinstance(claims, list):
        return []
    return [item for item in claims if isinstance(item, dict)]


def _claim_values(claims, *needles):
    found = []
    for claim in claims:
        typ = str(claim.get("typ") or "").casefold()
        if any(needle in typ for needle in needles):
            value = str(claim.get("val") or "").strip()
            if value:
                found.append(value)
    return found


def current_actor():
    if has_request_context() and getattr(g, "actor", None):
        return g.actor
    actor = resolve_actor()
    if has_request_context():
        g.actor = actor
    return actor


def resolve_actor():
    if not has_request_context():
        return {"name": "", "id": "", "role": default_role(), "signedIn": False}
    principal = _decode_principal(request.headers.get("X-MS-CLIENT-PRINCIPAL"))
    claims = _claims(principal)
    name = str(request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME") or "").strip()
    if not name:
        names = _claim_values(claims, "preferred_username", "upn", "emailaddress", "/name")
        name = names[0] if names else ""
    actor_id = str(request.headers.get("X-MS-CLIENT-PRINCIPAL-ID") or "").strip()
    if not actor_id:
        ids = _claim_values(claims, "objectidentifier", "oid")
        actor_id = ids[0] if ids else ""
    roles = [_normalize_role(value) for value in _claim_values(claims, "role")]
    roles = [role for role in roles if role]
    signed_in = bool(name or actor_id or principal)
    if roles:
        role = max(roles, key=lambda item: ROLE_RANK[item])
    elif signed_in:
        role = "viewer"
    else:
        role = default_role()
    return {
        "name": name[:160],
        "id": actor_id[:80],
        "role": role,
        "signedIn": signed_in,
    }


def enforce_access():
    if request.method == "OPTIONS" or request.path in OPEN_PATHS or not request.path.startswith("/api/"):
        return None
    actor = current_actor()
    if auth_required() and not actor["signedIn"]:
        return jsonify({"success": False, "message": "Sign in is required."}), 401
    if request.method not in SAFE_METHODS and ROLE_RANK[actor["role"]] < ROLE_RANK["editor"]:
        return jsonify({"success": False, "message": "This account can view records but cannot change them."}), 403
    return None
