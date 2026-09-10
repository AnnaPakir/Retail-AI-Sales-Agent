from fastapi import FastAPI, HTTPException

from .agent import SalesAgent
from .schemas import ChatRequest, ChatResponse, ExecutionTrace

app = FastAPI(
    title="Retail AI Sales Agent",
    version="0.1.0",
    description="Public, sanitized demo of a guarded retail assistant workflow.",
)
agent = SalesAgent()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return agent.handle(request)


@app.get("/v1/traces/{trace_id}", response_model=ExecutionTrace)
def get_trace(trace_id: str) -> ExecutionTrace:
    trace = agent.traces.get(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace
