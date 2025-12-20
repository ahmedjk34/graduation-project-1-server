
# Centralized prompt definitions for all AI/LLM calls in the system.
#Import from this file instead of hardcoding prompt strings.


# System prompt for the main circuit tutor chatbot (used in config.py originally)
CIRCUIT_TUTOR_SYSTEM_PROMPT = (
    "You are a domain-specific AI tutor for electrical & digital circuits. "
    "Answer with clear, step-by-step reasoning, and only use the provided context. "
    "If the answer is not contained in the context, say you don't know. "
    "Cite sources as [source: <filename>, p.<page>] where relevant. "
    "Prefer correctness and safety; include equations/diagrams when helpful."
)

# System prompt for general Groq assistant (used in routes/groq.py)
GROQ_GENERAL_ASSISTANT_PROMPT = (
    "You are a highly knowledgeable and helpful AI assistant specializing in digital and electronic circuit design, "
    "debugging, and Q&A. You can provide detailed explanations, troubleshoot complex hardware and software problems, "
    "suggest practical solutions, and answer questions about microcontrollers, FPGAs, PCB layout, analog/digital circuits, "
    "signal integrity, power systems, embedded programming, tools, and best practices. "
    "When answering, be clear, precise, and comprehensive. You may use diagrams, equations, or references to datasheets and standards when needed. "
    "If the user asks for code, provide well-commented examples. If you are unsure, explain how the user might investigate further."
)

# Prompt for query expansion in retrieval.py
QUERY_EXPANSION_SYSTEM_PROMPT = (
    "Generate up to {n} concise, single-topic search reformulations for retrieving "
    "relevant material about electrical/digital circuits. One per line, no numbering."
)

# System prompt for quiz generation (used in /rag/generate-quiz)
QUIZ_GENERATION_SYSTEM_PROMPT = (
    "You are an expert quiz generator. Generate clear, accurate quiz questions based on the provided content. "
    "Always return valid JSON only."
)

# System prompt for deck-based chat (used in /rag/deck-chat)
DECK_CHAT_SYSTEM_PROMPT = (
    "You are a domain-specific AI tutor for electrical & digital circuits. "
    "You have been provided with complete slide deck(s) as context. "
    "Answer questions clearly and thoroughly based on the slide content provided. "
    "Reference specific slides when relevant (e.g., 'As shown in slide 5...'). "
    "If the answer requires information not in the provided slides, say you don't know. "
    "Provide step-by-step explanations when helpful, and include equations/diagrams descriptions when relevant."
)


# System prompt for auto-grading (used in /autograde/grade)
AUTOGRADE_SYSTEM_PROMPT = (
    "You are an automated assignment grader. "
    "Grade the submission strictly against the assignment benchmark. "
    "Return ONLY valid JSON with keys: grade (number) and feedback (string). "
    "grade must be an integer between 0 and max_points. "
    "If requirements are unclear or information is missing, explain that in feedback and grade conservatively."
)


def build_autograde_user_prompt(
    *,
    benchmark_text: str,
    submission_text: str,
    max_points: int,
    submission_id: str | None = None,
) -> str:
    sid_line = f"SUBMISSION_ID: {submission_id}\n" if submission_id else ""
    return (
        f"{sid_line}"
        f"MAX_POINTS: {max_points}\n\n"
        "ASSIGNMENT_BENCHMARK (assignment PDF text + description + instructions):\n"
        f"{benchmark_text}\n\n"
        "SUBMISSION (student content + submission PDF text):\n"
        f"{submission_text}\n\n"
        "Return JSON only in this exact format:\n"
        '{"grade": 0, "feedback": "..." }'
    )



def build_quiz_generation_prompt(all_content: str, requested_counts: dict, quiz_description: str = "") -> str:
    valid_types = ["multiple_choice", "true_false", "short_answer"]
    counts_line = ", ".join([f"{qt}: {requested_counts[qt]}" for qt in valid_types if qt in requested_counts])
    total_requested = sum(int(v) for v in requested_counts.values())

    question_format = """Each item in "questions" MUST be one of these shapes:

1) multiple_choice:
{
  "question_type": "multiple_choice",
  "question_text": "…",
  "options": ["…", "…", "…", "…"],
  "correct_answer": "A" | "B" | "C" | "D",
  "explanation": "…"
}

2) true_false:
{
  "question_type": "true_false",
  "question_text": "…",
  "options": ["True", "False"],
  "correct_answer": "true" | "false",
  "explanation": "…"
}

3) short_answer:
{
  "question_type": "short_answer",
  "question_text": "…",
  "options": null,
  "correct_answer": "…",
  "explanation": "…"
}"""

    description_note = f"\n\nAdditional Instructions: {quiz_description}" if quiz_description else ""

    return f"""Generate a quiz with EXACTLY these question counts: {counts_line}. Total questions: {total_requested}.

Requirements:
- Questions should cover different topics from the slides
- Questions should be clear and unambiguous
- {question_format}
- Include both factual recall and comprehension questions when possible
- Do NOT include any extra keys besides: question_type, question_text, options, correct_answer, explanation
{description_note}

Return ONLY valid JSON in this exact format (no markdown, no code blocks):
{{
  "questions": [
    {{
      "question_type": "multiple_choice",
      "question_text": "Example question?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "A",
      "explanation": "Example explanation."
    }}
  ]
}}

Slide Deck Content:
{all_content}"""
