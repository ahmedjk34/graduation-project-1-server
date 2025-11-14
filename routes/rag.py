# server/routes/rag.py
from flask import Blueprint, request, jsonify
from rag.ingest import ingest_directory
from rag.retrieval import retrieve_context, generate_answer

rag_bp = Blueprint("rag", __name__)


# Ingests PDFs from data directory into ChromaDB
# Processes all PDFs, extracts text, chunks it, and stores with metadata
@rag_bp.route("/ingest", methods=["POST"])
def ingest():
    # 1. Parse request body for optional data_dir parameter
    body = request.get_json(silent=True) or {}
    data_dir = body.get("data_dir", "./data")
    # 2. Call ingestion pipeline and return summary
    try:
        summary = ingest_directory(data_dir=data_dir)
        return jsonify({
            "status": "ok",
            "summary": summary
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


# RAG-powered chat endpoint with source citations
# Retrieves relevant context, generates grounded answer using Groq, returns with sources
@rag_bp.route("/chat", methods=["POST"])
def rag_chat():
    # 1. Validate request is JSON
    if not request.is_json:
        return jsonify({"error": "Request must be JSON."}), 400
    # 2. Parse and validate question parameter
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({
            "error": "'question' must be non-empty."
        }), 400
    # 3. Parse optional parameters with defaults
    top_k = int(data.get("top_k", 5))
    expand = bool(data.get("use_query_expansion", True))
    # 4. Retrieve relevant context chunks
    try:
        ctx, used_queries = retrieve_context(
            question,
            top_k=top_k,
            use_query_expansion=expand
        )
        # 5. Generate answer using Groq with retrieved context
        gen = generate_answer(question, ctx)
        if "error" in gen:
            return jsonify({"error": gen["error"]}), 500
        # 6. Extract sources for UI display
        sources = [
            {"source": c["source"], "page": c["page"]}
            for c in ctx
        ]
        # 7. Return response with answer and sources
        return jsonify({
            "question": question,
            "used_queries": used_queries,
            "answer": gen["answer"],
            "sources": sources
        }), 200
    except Exception as e:
        return jsonify({
            "error": "RAG pipeline failed",
            "details": str(e)
        }), 500

