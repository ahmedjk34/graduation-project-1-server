# server/routes/rag.py
from flask import Blueprint, request, jsonify, Response
import json

from rag.ingest import ingest_directory
from rag.retrieval import retrieve_context, generate_answer, get_all_slides_from_decks, groq_client, build_slides_context
from rag.slide_ingest import ingest_pdf_deck, ingest_pptx_deck
from rag.ocr_adapter import get_ocr_adapter
from rag.prompts import QUIZ_GENERATION_SYSTEM_PROMPT, build_quiz_generation_prompt, DECK_CHAT_SYSTEM_PROMPT
from utils.llm_utils import extract_json_object

from config import GROQ_MODEL


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
        # 5. Extract sources for UI display
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
        
        # 6. Generate answer using Groq with retrieved context (returns Response for SSE)
        metadata = {
            "question": question,
            "used_queries": used_queries,
            "sources": sources
        }
        gen_response = generate_answer(question, ctx, metadata=metadata)
        
        # 7. Check if it's an error dict instead of Response
        if isinstance(gen_response, dict) and "error" in gen_response:
            return jsonify({"error": gen_response["error"]}), 500
        
        # 8. Return the SSE Response
        return gen_response
        
    except Exception as e:
        return jsonify({
            "error": "RAG pipeline failed",
            "details": str(e)
        }), 500


# Deck-based chat endpoint - retrieves ALL slides from specified decks
# and attaches them to every prompt (no semantic search/RAG)
@rag_bp.route("/deck-chat", methods=["POST"])
def deck_chat():
    # 1. Validate request is JSON
    if not request.is_json:
        return jsonify({"error": "Request must be JSON."}), 400

    # 2. Parse and validate parameters
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({
            "error": "'question' must be non-empty."
        }), 400
    
    deck_ids = data.get("deck_ids")
    if not deck_ids:
        return jsonify({"error": "'deck_ids' (array) is required."}), 400
    
    if not isinstance(deck_ids, list) or len(deck_ids) == 0:
        return jsonify({"error": "'deck_ids' must be a non-empty array."}), 400

    try:
        # 3. Retrieve ALL slides from specified decks (no semantic search)
        slides = get_all_slides_from_decks(deck_ids)
        
        if not slides:
            return jsonify({
                "error": f"No slides found for deck_ids: {deck_ids}"
            }), 404
        
        # 4. Format slides into context string
        all_slides_content = build_slides_context(slides)
        
        # 5. Build messages for Groq
        if groq_client is None:
            return jsonify({"error": "GROQ_API_KEY is missing or invalid."}), 500
        
        messages = [
            {
                "role": "system",
                "content": DECK_CHAT_SYSTEM_PROMPT
            },
            {
                "role": "system",
                "content": f"SLIDE DECK CONTENT:\n\n{all_slides_content}"
            },
            {
                "role": "user",
                "content": question
            }
        ]
        
        # 6. Format sources for response
        sources = []
        for slide in slides:
            sources.append({
                "source": slide.get("deck_id"),
                "slide_number": slide.get("slide_number"),
                "slide_title": slide.get("slide_title", ""),
                "chunk_type": "slide"
            })
        
        # 7. Generate answer using Groq with SSE streaming
        try:
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.2,
                stream=True,
            )
        except Exception as e:
            return jsonify({"error": "Error communicating with LLM provider.", "details": str(e)}), 502
        
        def SSE():
            # Send metadata first
            metadata = {
                "question": question,
                "deck_ids": deck_ids,
                "total_slides": len(slides),
                "sources": sources
            }
            yield f"event: metadata\ndata: {json.dumps(metadata)}\n\n"
            
            # Stream the response
            try:
                for chunk in response:
                    content = getattr(getattr(chunk.choices[0], "delta", None), "content", None)
                    if content:
                        # Convert em-spaces to newlines as safety measure [this bug took 2hours out of my life]
                        content = content.replace('\u2003', '\n')
                        yield f"data: {json.dumps(content)}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {str(e)}\n\n"

            yield "event: done\ndata: [DONE]\n\n"
        
        # 8. Return SSE response
        return Response(
            SSE(),
            mimetype='text/event-stream',
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    
    except Exception as e:
        return jsonify({
            "error": "Deck chat failed",
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


# Generates quiz questions from one or more slide decks
# Returns quiz in format ready to be stored in database
@rag_bp.route("/generate-quiz", methods=["POST"])
def generate_quiz():
    # 1. Validate request is JSON
    if not request.is_json:
        return jsonify({"error": "Request must be JSON."}), 400
    
    data = request.get_json(silent=True) or {}
    
    # 2. Validate required parameters
    deck_ids = data.get("deck_ids")
    if not deck_ids:
        return jsonify({"error": "'deck_ids' (array) is required."}), 400
    
    if not isinstance(deck_ids, list) or len(deck_ids) == 0:
        return jsonify({"error": "'deck_ids' must be a non-empty array."}), 400
    
    quiz_description = data.get("quiz_description", "")

    # 3. Parse/validate per-type question counts (required).
    # Expected shape:
    #   { "question_counts": { "multiple_choice": 3, "short_answer": 2, "true_false": 2 } }
    valid_types = ["multiple_choice", "true_false", "short_answer"]
    question_counts = data.get("question_counts")
    if question_counts is None:
        return jsonify({"error": "'question_counts' is required (object mapping question types to counts)."}), 400
    if not isinstance(question_counts, dict):
        return jsonify({"error": "'question_counts' must be an object mapping question types to counts."}), 400

    requested_counts = {}
    for qt, cnt in question_counts.items():
        if qt not in valid_types:
            return jsonify({
                "error": f"Invalid question type '{qt}'. Must be one of: {', '.join(valid_types)}"
            }), 400
        
        # Parse and validate count
        if cnt is None or isinstance(cnt, bool):
            parsed = None
        else:
            try:
                parsed = int(cnt)
                if parsed < 0:
                    parsed = None
            except Exception:
                parsed = None
        
        if parsed is None:
            return jsonify({"error": f"Count for '{qt}' must be a non-negative integer."}), 400
        requested_counts[qt] = parsed
    if not requested_counts or all(v == 0 for v in requested_counts.values()):
        return jsonify({"error": "'question_counts' must request at least one question (> 0)."}), 400
    
    try:

        # 4. Get all slides from all specified decks
        slides = get_all_slides_from_decks(deck_ids)
        
        if not slides:
            return jsonify({
                "error": f"No slides found for deck_ids: {deck_ids}"
            }), 404
        
        # 5. Format all slides into context for LLM
        all_content = build_slides_context(slides)
        
        # 6. Build quiz generation prompt
        quiz_prompt = build_quiz_generation_prompt(
            all_content=all_content,
            requested_counts=requested_counts,
            quiz_description=quiz_description,
        )
        
        # 8. Call Groq to generate quiz
        if groq_client is None:
            return jsonify({"error": "GROQ_API_KEY is missing or invalid."}), 500
        
        messages = [
            {
                "role": "system",
                "content": QUIZ_GENERATION_SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": quiz_prompt
            }
        ]
        
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.7,
        )
        
        quiz_text = response.choices[0].message.content.strip()
        
        # 9. Parse JSON from response
        try:
            quiz_json = extract_json_object(quiz_text)
        except Exception as e:
            return jsonify({
                "error": f"Failed to parse quiz JSON: {str(e)}",
                "raw_response": quiz_text
            }), 500
        
        # 10. Validate structure
        if "questions" not in quiz_json:
            return jsonify({
                "error": "Invalid quiz format: missing 'questions' field",
                "raw_response": quiz_text
            }), 500

        raw_questions = quiz_json.get("questions", [])
        if not isinstance(raw_questions, list):
            return jsonify({
                "error": "Invalid quiz format: 'questions' must be an array",
                "raw_response": quiz_text
            }), 500
        # 11. Minimal sanity checks (frontend/LLM are expected to follow the prompt).
        total_requested = sum(v for v in requested_counts.values() if v > 0)
        if len(raw_questions) != total_requested:
            return jsonify({
                "error": "LLM returned unexpected number of questions.",
                "expected": total_requested,
                "got": len(raw_questions),
                "raw_response": quiz_text
            }), 502

        for i, q in enumerate(raw_questions):
            if not isinstance(q, dict):
                return jsonify({"error": f"Invalid question at index {i}: must be an object."}), 502
            qt = q.get("question_type")
            if qt not in valid_types:
                return jsonify({"error": f"Invalid question_type at index {i}: {qt}"}), 502

        formatted_questions = []
        for idx, q in enumerate(raw_questions, start=1):
            formatted_questions.append({
                "question_text": q.get("question_text", ""),
                "question_type": q.get("question_type", ""),
                "options": q.get("options"),
                "correct_answer": q.get("correct_answer", ""),
                "points": 1, #will be overriden in front-end
                "order_index": idx,
                "explanation": q.get("explanation", ""),
            })

        response_question_type = "mixed"
        nonzero_types = [k for k, v in requested_counts.items() if v > 0]
        if len(nonzero_types) == 1:
            response_question_type = nonzero_types[0]

        # 12. Return quiz in database-ready format
        return jsonify({
            "deck_ids": deck_ids,
            "total_slides": len(slides),
            "question_count": len(formatted_questions),
            "question_type": response_question_type,
            "question_counts": requested_counts,
            "questions": formatted_questions
        }), 200
    
    except Exception as e:
        return jsonify({"error": f"Quiz generation failed: {str(e)}"}), 500
