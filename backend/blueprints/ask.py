from flask import Blueprint, jsonify, request

from config import ASK_MAX_QUESTION, llm_enabled
from db import get_connection
from logging_util import audit
from services.rag import (
    generate_answer,
    maybe_backfill_index,
    rag_status,
    reindex_all,
    retrieve_citations,
)

bp = Blueprint("ask", __name__)


@bp.get("/api/ask/status")
def ask_status():
    with get_connection() as conn:
        data = rag_status(conn)
    return jsonify({"success": True, "data": data})


@bp.post("/api/ask/reindex")
def ask_reindex():
    with get_connection() as conn:
        reindex_all(conn)
        data = rag_status(conn)
    audit("ask.reindex", summary=f"chunks={data['chunkCount']}")
    return jsonify({"success": True, "message": "Index rebuilt", "data": data})


@bp.post("/api/ask")
def ask_question():
    data = request.get_json(silent=True) or {}
    question = str(data.get("question") or data.get("q") or "").strip()
    if not question:
        audit("ask.query", "failure", summary="empty question")
        return jsonify({"success": False, "message": "A question is required."}), 400
    if len(question) > ASK_MAX_QUESTION:
        question = question[:ASK_MAX_QUESTION]
    with get_connection() as conn:
        indexing = maybe_backfill_index(conn)
        citations = retrieve_citations(conn, question)
    if indexing and not citations:
        audit("ask.query", summary=question[:200], extra={"mode": "indexing"})
        return jsonify({
            "success": True,
            "data": {
                "question": question,
                "answer": "Indexing wiki notes, files, and SOPs. Try Ask again in a moment.",
                "mode": "indexing",
                "citations": [],
                "llmEnabled": llm_enabled(),
                "llmError": None,
            },
        })
    wanted_generate = llm_enabled()
    answer, llm_error = generate_answer(question, citations)
    mode = "generate" if wanted_generate and not llm_error else "retrieve"
    if wanted_generate and llm_error:
        mode = "retrieve"
        if citations:
            answer = (
                "Could not reach Azure OpenAI, so here are the closest matches from the wiki and toolkit.\n\n"
                + "\n".join(
                    f"[{index}] {item['title']} ({item['locator']})\n{item['excerpt']}"
                    for index, item in enumerate(citations, start=1)
                )
            )
    audit(
        "ask.query",
        outcome="failure" if llm_error else "success",
        summary=question[:200],
        extra={"mode": mode, "llmError": llm_error or ""},
    )
    return jsonify({
        "success": True,
        "data": {
            "question": question,
            "answer": answer,
            "mode": mode,
            "citations": citations,
            "llmEnabled": llm_enabled(),
            "llmError": llm_error,
        },
    })
