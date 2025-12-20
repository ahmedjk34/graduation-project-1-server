from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from groq import Groq


def create_groq_client(api_key: Optional[str]) -> Optional[Groq]:
    key = (api_key or "").strip()
    if not key:
        return None
    try:
        return Groq(api_key=key)
    except Exception:
        return None


def truncate_middle(text: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    marker = "\n\n...[TRUNCATED]...\n\n"
    keep_tail = min(2500, max_chars // 3)
    keep_head = max_chars - keep_tail - len(marker)
    if keep_head <= 0:
        return text[:max_chars]
    return text[:keep_head] + marker + text[-keep_tail:]


def extract_json_object(text: str) -> Dict[str, Any]:
    s = (text or "").strip()
    if not s:
        raise ValueError("Empty response; no JSON object found.")

    # Fast path: direct JSON.
    try:
        parsed = json.loads(s)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Scan for the first decodable JSON object anywhere in the text (handles code-fences and chatter).
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", s):
        idx = match.start()
        try:
            parsed, _ = decoder.raw_decode(s[idx:])
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("No JSON object found in response text.")

