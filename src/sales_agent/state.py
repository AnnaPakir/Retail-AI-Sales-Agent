from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class DialogState:
    pending_product_id: str | None = None


class DialogStateStore:
    def __init__(self) -> None:
        self._items: dict[str, DialogState] = {}
        self._lock = Lock()

    def get(self, session_id: str) -> DialogState:
        with self._lock:
            return self._items.setdefault(session_id, DialogState())

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._items.pop(session_id, None)
