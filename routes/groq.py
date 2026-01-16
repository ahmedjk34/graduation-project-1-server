from flask import Blueprint, Response, request, jsonify
import json
from config import GROQ_API_KEY
from rag.prompts import GROQ_GENERAL_ASSISTANT_PROMPT
from utils.llm_utils import create_groq_client

client = create_groq_client(GROQ_API_KEY)

groq_bp = Blueprint('groq', __name__)

@groq_bp.route('/general-llm', methods=['POST'])
def call_llm():
    
    #initial error check
    if client is None:
        return jsonify({"error": "LLM provider not configured. Missing or invalid GROQ_API_KEY."}), 500
    
    if not request.is_json:
        return jsonify({"error": "Request must be JSON with a 'prompt' field."}), 400

    data = request.get_json(silent=True)

    user_prompt = data.get('prompt')
    if user_prompt is None or not user_prompt.strip():
        return jsonify({"error": "'prompt' must be a non-empty value."}), 400

    user_prompt = user_prompt.strip()

    messages = [
        {"role": "system", "content": GROQ_GENERAL_ASSISTANT_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = client.chat.completions.create(
            messages=messages,
            model="moonshotai/kimi-k2-instruct-0905",
            stream=True,
        )
    except Exception as e:
            return jsonify({"error": "Error communicating with LLM provider.", "details": str(e)}), 502
    def SSE():
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
