# server/routes/rag.py
from flask import Blueprint, request, jsonify
from rag.ingest import ingest_directory
from rag.retrieval import retrieve_context, generate_answer
from rag.slide_ingest import ingest_pdf_deck, ingest_pptx_deck
from rag.ocr_adapter import get_ocr_adapter


rag_bp = Blueprint("rag", __name__)


# Ingests PDFs from data directory into ChromaDB
# Processes all PDFs, extracts text, chunks it, and stores with metadata
# This one processes all the PDFs in the data directory
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
        sources = []
        for c in ctx:
            source_info = {"source": c.get("source", "unknown")}
            if c.get("chunk_type") == "slide":
                source_info["slide_number"] = c.get("slide_number")
                source_info["chunk_type"] = "slide"
            elif c.get("chunk_type") == "window":
                source_info["start_slide"] = c.get("start_slide")
                source_info["end_slide"] = c.get("end_slide")
                source_info["chunk_type"] = "window"
            else:
                source_info["page"] = c.get("page")
            sources.append(source_info)
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


# Ingests slide decks (PDF or PPTX) into ChromaDB
# Accepts file upload with explicit file_type parameter
@rag_bp.route("/ingest-slides", methods=["POST"])
def ingest_slides():
    
    # 1. Check if file is present
    if 'file' not in request.files:
        return jsonify({
            "status": "error",
            "error": "No file provided. Use 'file' field in multipart/form-data."
        }), 400
    
    # 2. parse the file
    file = request.files['file']
    if file.filename == '':
        return jsonify({
            "status": "error",
            "error": "Empty filename provided."
        }), 400
    
    # 3. Get file_type (required)
    file_type = request.form.get('file_type', '').lower().strip()
    if file_type not in ['pdf', 'pptx']:
        return jsonify({
            "status": "error",
            "error": "file_type must be 'pdf' or 'pptx'"
        }), 400
    
    # 4. Get optional deck_id [in case we want to save into the db a specific deck id, otherwise it will be automatically generated]
    deck_id = request.form.get('deck_id', None)
    if deck_id:
        deck_id = deck_id.strip()
    
    # 5. Read file bytes
    try:
        file_bytes = file.read()
        if not file_bytes:
            return jsonify({
                "status": "error",
                "error": "File is empty."
            }), 400
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": f"Failed to read file: {str(e)}"
        }), 400
    
    # 6. Get OCR adapter 
    ocr_adapter = get_ocr_adapter()
    
    # 7. Ingest based on file type
    try:
        
        if file_type == 'pdf':
            result = ingest_pdf_deck(
                file_bytes=file_bytes,
                deck_id=deck_id,
                ocr_adapter=ocr_adapter,
                store_in_db=True
            )
        else:  # pptx
            result = ingest_pptx_deck(
                file_bytes=file_bytes,
                deck_id=deck_id,
                ocr_adapter=ocr_adapter,
                store_in_db=True
            )
        
        return jsonify({
            "status": "ok",
            "deck_id": result["deck_id"],
            "slides_processed": result["slides_processed"],
            "slide_chunks": result["slide_chunks_count"],
            "window_chunks": result["window_chunks_count"],
            "stored_count": result["stored_count"],
            "ocr_stats": result["ocr_stats"],
            "warnings": result["warnings"]
        }), 200
    
    except ImportError as e:
        return jsonify({
            "status": "error",
            "error": f"Missing dependency: {str(e)}"
        }), 500
    except ValueError as e:
        return jsonify({
            "status": "error",
            "error": f"Invalid file format: {str(e)}"
        }), 400
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": f"Ingestion failed: {str(e)}"
        }), 500

