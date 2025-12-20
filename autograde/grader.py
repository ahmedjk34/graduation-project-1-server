from __future__ import annotations

import re
from typing import Any, Dict, Optional

from config import GROQ_API_KEY, GROQ_MODEL
from rag.prompts import AUTOGRADE_SYSTEM_PROMPT, build_autograde_user_prompt
from utils.llm_utils import create_groq_client, extract_json_object, truncate_middle


groq_client = create_groq_client(GROQ_API_KEY)


def grade_submission(
    *,
    benchmark_text: str,
    submission_text: str,
    max_points: int,
    submission_id: Optional[str] = None,
) -> Dict[str, Any]:
    if groq_client is None:
        return {"error": "LLM provider not configured. Missing or invalid GROQ_API_KEY."}

    benchmark_text = truncate_middle(benchmark_text, max_chars=12_000)
    submission_text = truncate_middle(submission_text, max_chars=12_000)

    user_prompt = build_autograde_user_prompt(
        benchmark_text=benchmark_text,
        submission_text=submission_text,
        max_points=max_points,
        submission_id=submission_id,
    )

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": AUTOGRADE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
    except Exception as e:
        return {"error": "Error communicating with LLM provider.", "details": str(e)}

    raw_text = response.choices[0].message.content if response.choices else ""
    try:
        parsed = extract_json_object(raw_text)
    except Exception as e:
        return {"error": "Failed to parse LLM JSON response.", "details": str(e), "raw_response": raw_text}

    grade_raw = parsed.get("grade")
    feedback = parsed.get("feedback")

    grade_val = None
    if isinstance(grade_raw, (int, float)) and not isinstance(grade_raw, bool):
        grade_val = int(round(float(grade_raw)))
    elif isinstance(grade_raw, str):
        match = re.search(r"-?\d+(?:\.\d+)?", grade_raw)
        if match:
            try:
                grade_val = int(round(float(match.group())))
            except Exception:
                grade_val = None

    if grade_val is None:
        return {"error": "LLM returned invalid 'grade'.", "raw_response": raw_text}

    if grade_val < 0:
        grade_val = 0
    if grade_val > max_points:
        grade_val = max_points

    if not isinstance(feedback, str):
        feedback = "" if feedback is None else str(feedback)

    return {"grade": grade_val, "feedback": feedback.strip()}
