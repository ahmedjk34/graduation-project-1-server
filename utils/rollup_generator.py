import json
from typing import List, Dict, Optional
from config import GROQ_API_KEY, GROQ_MODEL
from rag.prompts import ROLLUP_MEMORY_SYSTEM_PROMPT
from utils.llm_utils import create_groq_client


_rollup_client = create_groq_client(GROQ_API_KEY)



def generate_rollup_memory(
    existing_rollup: Optional[str],
    messages_to_rollup: List[Dict],
) -> str:

    if _rollup_client is None:
        raise ValueError("Rollup client is not initialized")
    
    # Format messages as JSON for the prompt
    messages_json = json.dumps(messages_to_rollup, indent=2, ensure_ascii=False)
    existing_rollup_text = existing_rollup or "(empty)"
    
    # Build the user prompt with the actual data
    user_prompt = (
        "EXISTING_ROLLUP_MEMORY:\n"
        f"{existing_rollup_text}\n\n"
        "MESSAGES_TO_ROLLUP:\n"
        f"{messages_json}"
    )
    
    try:
        response = _rollup_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": ROLLUP_MEMORY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2, #Temp is on the lower side to be more consistent, yet it still has a bit of randomness / creativity
        )
        
        rollup_text = response.choices[0].message.content.strip()
        return rollup_text
    except Exception as e:
        # Fallback on error
        print(f"Rollup generation failed: {e}")
        return ""


