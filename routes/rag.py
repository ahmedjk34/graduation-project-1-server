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
    
    question_count = int(data.get("question_count", 10))
    question_type = data.get("question_type", "multiple_choice")
    quiz_description = data.get("quiz_description", "")
    
    # 3. Validate question_type
    valid_types = ["multiple_choice", "true_false", "short_answer"]
    if question_type not in valid_types:
        return jsonify({
            "error": f"'question_type' must be one of: {', '.join(valid_types)}"
        }), 400
    
    try:
        from rag.retrieval import get_all_slides_from_decks, groq_client
        from config import GROQ_MODEL
        import json
        import re
        
        # 4. Get all slides from all specified decks
        slides = get_all_slides_from_decks(deck_ids)
        
        if not slides:
            return jsonify({
                "error": f"No slides found for deck_ids: {deck_ids}"
            }), 404
        
        # 5. Format all slides into context for LLM
        slide_texts = []
        for slide in slides:
            slide_num = slide.get("slide_number", 0)
            slide_title = slide.get("slide_title", "")
            slide_text = slide.get("text", "")
            deck_id = slide.get("deck_id", "")
            slide_texts.append(f"--- DECK: {deck_id} | SLIDE {slide_num}: {slide_title} ---\n{slide_text}")
        
        all_content = "\n\n".join(slide_texts)
        
        # 6. Build prompt based on question type
        if question_type == "multiple_choice":
            question_format = """For each question, provide:
- question_text: The question text
- options: JSON array of exactly 4 options (e.g., ["Option A text", "Option B text", "Option C text", "Option D text"])
- correct_answer: The letter of the correct answer ("A", "B", "C", or "D")
- explanation: Brief explanation (1-2 sentences) of why this answer is correct"""
            
            example = """{
      "question_text": "What is the main topic discussed in the slides?",
      "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
      "correct_answer": "A",
      "explanation": "This is correct because..."
    }"""
        
        elif question_type == "true_false":
            question_format = """For each question, provide:
- question_text: The statement (should be clearly true or false)
- options: JSON array with exactly 2 options: ["True", "False"]
- correct_answer: Either "true" or "false" (lowercase)
- explanation: Brief explanation (1-2 sentences) of why this answer is correct"""
            
            example = """{
      "question_text": "The concept discussed in slide 5 is fundamental to understanding the topic.",
      "options": ["True", "False"],
      "correct_answer": "true",
      "explanation": "This is correct because..."
    }"""
        
        else:  # short_answer
            question_format = """For each question, provide:
- question_text: The question text
- options: null (not used for short answer)
- correct_answer: The expected answer text
- explanation: Brief explanation (1-2 sentences) of the answer"""
            
            example = """{
      "question_text": "What is the main concept introduced in slide 3?",
      "options": null,
      "correct_answer": "The main concept is...",
      "explanation": "This is correct because..."
    }"""
        
        # 7. Build quiz generation prompt
        description_note = f"\n\nAdditional Instructions: {quiz_description}" if quiz_description else ""
        
        quiz_prompt = f"""Generate {question_count} {question_type.replace('_', ' ')} quiz questions based on the following slide deck content.

Requirements:
- Questions should cover different topics from the slides
- Questions should be clear and unambiguous
- {question_format}
- Include both factual recall and comprehension questions when possible
{description_note}

Return ONLY valid JSON in this exact format (no markdown, no code blocks):
{{
  "questions": [
    {example}
  ]
}}

Slide Deck Content:
{all_content}"""
        
        # 8. Call Groq to generate quiz
        if groq_client is None:
            return jsonify({"error": "GROQ_API_KEY is missing or invalid."}), 500
        
        messages = [
            {
                "role": "system",
                "content": "You are an expert quiz generator. Generate clear, accurate quiz questions based on the provided content. Always return valid JSON only."
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
        
        # 9. Parse JSON from response (clean up if needed)
        quiz_text = re.sub(r'```json\s*', '', quiz_text)
        quiz_text = re.sub(r'```\s*', '', quiz_text)
        quiz_text = quiz_text.strip()
        
        try:
            quiz_json = json.loads(quiz_text)
        except json.JSONDecodeError:
            # Try to find JSON object in response
            json_match = re.search(r'\{.*\}', quiz_text, re.DOTALL)
            if json_match:
                quiz_json = json.loads(json_match.group())
            else:
                raise ValueError("No valid JSON found in LLM response")
        
        # 10. Validate structure
        if "questions" not in quiz_json:
            return jsonify({
                "error": "Invalid quiz format: missing 'questions' field",
                "raw_response": quiz_text[:500]
            }), 500
        
        # 11. Transform to database-ready format
        # Add order_index and points to each question
        formatted_questions = []
        for idx, q in enumerate(quiz_json.get("questions", []), start=1):
            formatted_q = {
                "question_text": q.get("question_text", ""),
                "question_type": question_type,
                "options": q.get("options"),  # JSONB - can be array or null
                "correct_answer": q.get("correct_answer", ""),
                "points": 1,  # Default, can be customized
                "order_index": idx,
                "explanation": q.get("explanation", "")
            }
            formatted_questions.append(formatted_q)
        
        # 12. Return quiz in database-ready format
        return jsonify({
            "deck_ids": deck_ids,
            "total_slides": len(slides),
            "question_count": len(formatted_questions),
            "question_type": question_type,
            "questions": formatted_questions
        }), 200
    
    except json.JSONDecodeError as e:
        return jsonify({
            "error": f"Failed to parse quiz JSON: {str(e)}",
            "raw_response": quiz_text[:500] if 'quiz_text' in locals() else "N/A"
        }), 500
    except Exception as e:
        return jsonify({"error": f"Quiz generation failed: {str(e)}"}), 500

