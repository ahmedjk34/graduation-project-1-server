from flask import Blueprint, request, jsonify
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    client = None
else:
    try:
        client = Groq(api_key=api_key)
    except Exception:
        client = None

groq_bp = Blueprint('groq', __name__)

CONTEXT = (
    "You are a highly knowledgeable and helpful AI assistant specializing in digital and electronic circuit design, "
    "debugging, and Q&A. You can provide detailed explanations, troubleshoot complex hardware and software problems, "
    "suggest practical solutions, and answer questions about microcontrollers, FPGAs, PCB layout, analog/digital circuits, "
    "signal integrity, power systems, embedded programming, tools, and best practices. "
    "When answering, be clear, precise, and comprehensive. You may use diagrams, equations, or references to datasheets and standards when needed. "
    "If the user asks for code, provide well-commented examples. If you are unsure, explain how the user might investigate further."
)

@groq_bp.route('/llm', methods=['POST'])
def call_llm():
    
    #initial error check
    if client is None:
        return jsonify({"error": "LLM provider not configured. Missing or invalid GROQ_API_KEY."}), 500
    
    if not request.is_json:
        return jsonify({"error": "Request must be JSON with a 'prompt' field."}), 400

    data = request.get_json(silent=True)
    print(data)

    user_prompt = data.get('prompt')
    if user_prompt is None or not user_prompt.strip():
        return jsonify({"error": "'prompt' must be a non-empty value."}), 400

    user_prompt = user_prompt.strip()

    messages = [
        {"role": "system", "content": CONTEXT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = client.chat.completions.create(
            messages=messages,
            model="moonshotai/kimi-k2-instruct-0905",
        )
    except Exception as e:
        return jsonify({"error": "Error communicating with LLM provider.", "details": str(e)}), 502

    answer = None

    #Proper parsing of response
    try:
        choices = response.choices if hasattr(response, "choices") else (response.get("choices") if isinstance(response, dict) else None)
        if choices and len(choices) > 0:
            first = choices[0]
            if hasattr(first, "message") and hasattr(first.message, "content"):
                answer = first.message.content
            elif isinstance(first, dict):
                answer = first.get("message", {}).get("content") or first.get("text")
            elif hasattr(first, "text"):
                answer = first.text
    except Exception:
        answer = None

    if not answer:
        return jsonify({"error": "No answer returned from LLM provider."}), 502

    return jsonify({"prompt": user_prompt, "answer": answer}), 200