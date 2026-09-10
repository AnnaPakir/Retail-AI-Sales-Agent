from __future__ import annotations

import re
from threading import Lock

from .schemas import ExecutionTrace


def redact_personal_data(text: str) -> str:
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[EMAIL]", text)
    text = re.sub(r"(?:\+7|8)[\s()-]*\d{3}[\s()-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}", "[PHONE]", text)
    text = re.sub(r"(?i)(заказ\s*[№#]?\s*)\d{4,}", r"\1[ORDER_ID]", text)
    return text


class TraceStore:
    def __init__(self) -> None:
        self._items: dict[str, ExecutionTrace] = {}
        self._lock = Lock()

    def save(self, trace: ExecutionTrace) -> None:
        with self._lock:
            self._items[trace.trace_id] = trace

    def get(self, trace_id: str) -> ExecutionTrace | None:
        return self._items.get(trace_id)
