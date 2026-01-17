# Will create a centerlized, in memory, storage & session management system for the entire app
# Now yes, I obviously could have saved the conversions in the database [for true persistence]
# I do think it's much more performative, and to be honest, if this was truly a production grade app that I would have done
# I would have created two N VPS instanced,  (e.g. 2 instances one main one backup) and a last resort DB call in case session could not be found
# If i still have time, might implement the DB backup, if don't well. That's life for ya.

from typing import Dict, List, Optional
from dataclasses import dataclass, field
import threading

# Maximum number of raw messages to keep before triggering rollup
MAX_RAW_MESSAGES = 30

# PSEDUO CODE / IDEA
# 1. A centerlized storage using a singleton class
# 2. Each conversation is a session, and each session has a list of messages
# 3. Each message is a dict with a role and content
# 4. Each session has a rollup memory, which is a string that is the rollup of the previous messages
# 5. Each session has a max number of messages, and if the number of messages exceeds the max, the oldest messages are removed
# 6. Each session has a rollup generator, which is a function that generates the rollup memory
# 7. Each session has a rollup memory, which is a string that is the rollup of the previous messages
# 8. Each session has a rollup generator, which is a function that generates the rollup memory
# 9. Each session has a rollup memory, which is a string that is the rollup of the previous messages


@dataclass
class ConversationSession:
    session_id: str
    messages: List[Dict] = field(default_factory=list)
    rollup_memory: Optional[str] = None


class ConversationStorage:
    
    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}
        self._lock = threading.Lock()
    
    def get_or_create_session(self, session_id: str) -> ConversationSession:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = ConversationSession(session_id=session_id)
            return self._sessions[session_id]
    
    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        with self._lock:
            return self._sessions.get(session_id)
    
    def add_message(self, session_id: str, role: str, content: str) -> ConversationSession:
        session = self.get_or_create_session(session_id)
        with self._lock:
            session.messages.append({"role": role, "content": content})
        return session
    
    def update_rollup(self, session_id: str, rollup_memory: str):
        session = self.get_or_create_session(session_id)
        with self._lock:
            session.rollup_memory = rollup_memory
    
    def remove_messages(self, session_id: str, count: int):
        session = self.get_or_create_session(session_id)
        with self._lock:
            session.messages = session.messages[count:]
    
    def clear_session(self, session_id: str):
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]


# Global singleton instance
storage = ConversationStorage()


def get_storage() -> ConversationStorage:
    return storage
