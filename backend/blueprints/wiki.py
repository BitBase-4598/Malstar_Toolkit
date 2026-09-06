from flask import Blueprint, jsonify, request

from logging_util import audit
from services.wiki import get_page, list_pages, rebuild_wiki, search_wiki, wiki_status
from db import get_connection

bp = Blueprint("wiki", __name__)


@bp.get("/api/wiki/status")
def wiki_status_route():
    with get_connection() as conn:
        data = wiki_status(conn)
    return jsonify({"success": True, "data": data})


@bp.get("/api/wiki")
def wiki_list():
    payload = list_pages(
        query=str(request.args.get("q") or "").strip(),
        source_type=str(request.args.get("sourceType") or "").strip(),
        page=request.args.get("page", 1, type=int),
        page_size=request.args.get("pageSize", 40, type=int),
    )
    return jsonify({"success": True, **payload})


@bp.get("/api/wiki/search")
def wiki_search_route():
    question = str(request.args.get("q") or request.args.get("question") or "").strip()
    if not question:
        return jsonify({"success": False, "message": "A search query is required."}), 400
    hits = search_wiki(question)
    audit("wiki.search", summary=question[:200], extra={"hits": len(hits)})
    return jsonify({"success": True, "data": hits})


@bp.get("/api/wiki/<slug>")
def wiki_detail(slug):
    page = get_page(slug)
    if not page:
        return jsonify({"success": False, "message": "Wiki page not found."}), 404
    return jsonify({"success": True, "data": page})


@bp.post("/api/wiki/reindex")
def wiki_reindex():
    data = rebuild_wiki()
    audit("wiki.reindex", summary=f"pages={data['pageCount']} chunks={data['chunkCount']}")
    return jsonify({"success": True, "message": "Wiki rebuilt", "data": data})
