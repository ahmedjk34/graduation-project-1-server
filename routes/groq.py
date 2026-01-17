from flask import Blueprint, Response, request, jsonify
import json
from config import GROQ_API_KEY
from rag.prompts import GROQ_GENERAL_ASSISTANT_PROMPT
from utils.llm_utils import create_groq_client
from utils.conversation_storage import get_storage
from utils.conversation_builder import build_conversation_messages

client = create_groq_client(GROQ_API_KEY)

groq_bp = Blueprint('groq', __name__)


@groq_bp.route('/general-llm', methods=['POST'])
def call_llm():
    
    #initial error check
    if client is None:
        return jsonify({"error": "LLM provider not configured. Missing or invalid GROQ_API_KEY."}), 500
    
    if not request.is_json:
        return jsonify({"error": "Request must be JSON."}), 400

    data = request.get_json(silent=True) or {}
    
    # Support both old format (prompt) and new format (messages + session_id)
    user_prompt = data.get('prompt')
    messages_array = data.get('messages')  # Optional: array of {role, content}
    session_id = data.get('session_id')  # Optional: for conversation management
    
    # Validate input
    if not user_prompt and not messages_array:
        return jsonify({"error": "Either 'prompt' or 'messages' must be provided."}), 400
    
    if user_prompt and not user_prompt.strip():
        return jsonify({"error": "'prompt' must be a non-empty value."}), 400
    
    if messages_array:
        if not isinstance(messages_array, list):
            return jsonify({"error": "'messages' must be an array."}), 400
        if not messages_array:
            return jsonify({"error": "'messages' array cannot be empty."}), 400
        # Validate message format
        for msg in messages_array:
            if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
                return jsonify({"error": "Each message must have 'role' and 'content' fields."}), 400
    
    # Build messages with fixed window + rollup logic
    try:
        base_messages = [{"role": "system", "content": GROQ_GENERAL_ASSISTANT_PROMPT}]
        messages = build_conversation_messages(
            session_id=session_id,
            user_message=user_prompt.strip() if user_prompt else None,
            messages_array=messages_array,
            base_messages=base_messages
        )
        
        # If user_prompt was provided (incremental mode), add it back since shared function removes it
        # (This allows the caller to format it differently if needed, but in this case we use it as-is)
        if user_prompt and not messages_array:
            messages.append({"role": "user", "content": user_prompt.strip()})
    except Exception as e:
        return jsonify({"error": "Error building conversation context.", "details": str(e)}), 500

    try:
        response = client.chat.completions.create(
            messages=messages,
            model="moonshotai/kimi-k2-instruct-0905",
            stream=True,
        )
    except Exception as e:
        return jsonify({"error": "Error communicating with LLM provider.", "details": str(e)}), 502
    
    # Accumulator for storing full assistant response
    assistant_response = ""
    
    def SSE():
        nonlocal assistant_response
        try:
            for chunk in response:
                content = getattr(getattr(chunk.choices[0], "delta", None), "content", None)
                if content:
                    # Convert em-spaces to newlines as safety measure [this bug took 2hours out of my life]
                    content = content.replace('\u2003', '\n')
                    assistant_response += content
                    yield f"data: {json.dumps(content)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"
        finally:
            # Store assistant response in session if session_id is provided
            if session_id and assistant_response:
                storage = get_storage()
                storage.add_message(session_id, "assistant", assistant_response)
            
            yield "event: done\ndata: [DONE]\n\n"

    return Response(
        SSE(),
        mimetype='text/event-stream',
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )



    # #Proper parsing of response
    # try:
    #     choices = response.choices if hasattr(response, "choices") else (response.get("choices") if isinstance(response, dict) else None)
    #     if choices and len(choices) > 0:
    #         first = choices[0]
    #         if hasattr(first, "message") and hasattr(first.message, "content"):
    #             answer = first.message.content
    #         elif isinstance(first, dict):
    #             answer = first.get("message", {}).get("content") or first.get("text")
    #         elif hasattr(first, "text"):
    #             answer = first.text
    # except Exception:
    #     answer = None

    # if not answer:
    #     return jsonify({"error": "No answer returned from LLM provider."}), 502

    # return jsonify({"prompt": user_prompt, "answer": answer}), 200
