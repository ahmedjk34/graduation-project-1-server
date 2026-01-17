# This function builds LLM message arrays with conversation history and rollup memory management.
# It handles both single-turn (no session) and multi-turn (with session) conversation modes.
#
# PSEUDO CODE ALGORITHM:
#
# 1. INITIALIZE:
#    - If base_messages is None, set to empty list
#    - Create messages = copy of base_messages (system prompts, context, etc.)
#
# 2. CHECK SESSION MODE:
#    - If session_id is None:
#      2A. SINGLE-TURN MODE (backward compatible):
#          - If user_message provided: append {"role": "user", "content": user_message}
#          - If messages_array provided: filter out system messages and append each to messages
#          - Return messages immediately
#    - Else: proceed to session-based conversation management
#
# 3. SESSION-BASED CONVERSATION MANAGEMENT:
#    - Get conversation storage singleton
#    - Get or create session for session_id
#
#    3A. HANDLE messages_array (stateless pattern - frontend sends full history):
#        - Filter out system messages from messages_array → conversation_messages
#        - If len(conversation_messages) > MAX_RAW_MESSAGES:
#          - Calculate overflow_count = len(conversation_messages) - MAX_RAW_MESSAGES
#          - Split: messages_to_rollup = first overflow_count messages
#          - Split: raw_messages = last MAX_RAW_MESSAGES messages
#          - Generate new_rollup = rollup_generator(existing_rollup + messages_to_rollup)
#          - Update session.rollup_memory = new_rollup
#          - Update session.messages = raw_messages
#        - Else (no rollup needed):
#          - Update session.messages = conversation_messages
#        - If session.rollup_memory exists:
#          - Append {"role": "user", "content": "[Previous conversation context]\n{rollup_memory}"}
#        - Append all messages from session.messages (conversation history)
#
#    3B. HANDLE user_message (incremental mode):
#        - Add user_message to session.messages as {"role": "user", "content": user_message}
#        - If len(session.messages) > MAX_RAW_MESSAGES:
#          - Calculate overflow_count = len(session.messages) - MAX_RAW_MESSAGES
#          - Split: messages_to_rollup = first overflow_count messages
#          - Generate new_rollup = rollup_generator(existing_rollup + messages_to_rollup)
#          - Update session.rollup_memory = new_rollup
#          - Remove first overflow_count messages from session.messages
#        - If session.rollup_memory exists:
#          - Append {"role": "user", "content": "[Previous conversation context]\n{rollup_memory}"}
#        - Append all messages from session.messages (includes the user_message we added)
#        - If last message in messages is the user_message we added:
#          - Remove it (caller will add it back if needed, possibly formatted differently)
#
# 4. RETURN messages array ready for LLM API call

from typing import List, Dict, Optional
from utils.conversation_storage import get_storage, MAX_RAW_MESSAGES
from utils.rollup_generator import generate_rollup_memory


def build_conversation_messages(
    session_id: Optional[str] = None,
    user_message: Optional[str] = None,
    messages_array: Optional[List[Dict]] = None,
    base_messages: Optional[List[Dict]] = None
) -> List[Dict]:
    if base_messages is None:
        base_messages = []

    messages = base_messages.copy()

    if not session_id:
        if user_message:
            messages.append({"role": "user", "content": user_message})
        elif messages_array:
            for msg in messages_array:
                if msg.get("role") != "system":
                    messages.append(msg)
        return messages

    storage = get_storage()
    session = storage.get_or_create_session(session_id)

    if messages_array:
        conversation_messages = [msg for msg in messages_array if msg.get("role") != "system"]

        if len(conversation_messages) > MAX_RAW_MESSAGES:
            overflow_count = len(conversation_messages) - MAX_RAW_MESSAGES
            messages_to_rollup = conversation_messages[:overflow_count]
            raw_messages = conversation_messages[overflow_count:]

            new_rollup = generate_rollup_memory(
                existing_rollup=session.rollup_memory,
                messages_to_rollup=messages_to_rollup
            )

            storage.update_rollup(session_id, new_rollup)
            session.messages = raw_messages.copy()
        else:
            session.messages = conversation_messages.copy()

        if session.rollup_memory:
            messages.append({
                "role": "user",
                "content": f"[Previous conversation context]\n{session.rollup_memory}"
            })

        messages.extend(session.messages)

    elif user_message:
        storage.add_message(session_id, "user", user_message)
        session = storage.get_session(session_id)

        if len(session.messages) > MAX_RAW_MESSAGES:
            overflow_count = len(session.messages) - MAX_RAW_MESSAGES
            messages_to_rollup = session.messages[:overflow_count]

            new_rollup = generate_rollup_memory(
                existing_rollup=session.rollup_memory,
                messages_to_rollup=messages_to_rollup
            )

            storage.update_rollup(session_id, new_rollup)
            storage.remove_messages(session_id, overflow_count)
            session = storage.get_session(session_id)

        if session.rollup_memory:
            messages.append({
                "role": "user",
                "content": f"[Previous conversation context]\n{session.rollup_memory}"
            })

        messages.extend(session.messages)

        if messages and messages[-1].get("role") == "user" and messages[-1].get("content") == user_message:
            messages.pop()

    return messages
