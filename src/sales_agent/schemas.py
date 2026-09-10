from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Intent(StrEnum):
    CONSULTATION = "consultation"
    PRICE = "price"
    STOCK = "stock"
    PURCHASE = "purchase"
    PURCHASE_CONFIRMATION = "purchase_confirmation"
    EXISTING_ORDER = "existing_order"
    REPAIR = "repair"
    HUMAN_REQUEST = "human_request"
    WHOLESALE = "wholesale"
    DISCOUNT = "discount"
    SPARE_PARTS = "spare_parts"
    TRANSPARENCY = "transparency"
    UNSUPPORTED_ACTION = "unsupported_action"
    CLOSING = "closing"
    AMBIGUOUS = "ambiguous"


class Action(StrEnum):
    ANSWER = "answer"
    ASK_CLARIFICATION = "ask_clarification"
    ASK_CONFIRMATION = "ask_confirmation"
    HUMAN_HANDOFF = "human_handoff"
    END_DIALOGUE = "end_dialogue"


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|operator)$")
    content: str


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=8_000)
    request_id: str | None = Field(default=None, max_length=128)
    history: list[ChatMessage] = Field(default_factory=list, max_length=30)


class SourceRef(BaseModel):
    id: str
    title: str


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, str]
    result: dict[str, object]


class ChatResponse(BaseModel):
    trace_id: str
    intent: Intent
    action: Action
    response: str
    sources: list[SourceRef] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)


class TraceEvent(BaseModel):
    step: str
    data: dict[str, object]


class ExecutionTrace(BaseModel):
    trace_id: str
    session_id: str
    request_id: str | None
    redacted_message: str
    events: list[TraceEvent] = Field(default_factory=list)
