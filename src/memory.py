from __future__ import annotations

import threading
from collections import defaultdict, deque


class ConversationMemory:
    """교육용 인메모리 장기 문맥. 운영에서는 LangGraph Store/Redis로 교체한다."""

    def __init__(self, max_turns: int = 6):
        self._items: dict[str, deque[tuple[str, str]]] = defaultdict(
            lambda: deque(maxlen=max_turns)
        )
        self._lock = threading.Lock()

    def add(self, session_id: str, question: str, answer: str) -> None:
        with self._lock:
            self._items[session_id].append((question, answer[:800]))

    def summary(self, session_id: str) -> str:
        with self._lock:
            turns = list(self._items.get(session_id, []))
        if not turns:
            return ""
        return "\n".join(f"Q: {q}\nA: {a}" for q, a in turns[-3:])

