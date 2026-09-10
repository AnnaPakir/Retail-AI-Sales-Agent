from fastapi.testclient import TestClient

from sales_agent.api import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_and_trace() -> None:
    response = client.post(
        "/v1/chat",
        json={
            "session_id": "api-test",
            "request_id": "api-event-1",
            "message": "Цена A101, мой телефон +7 999 123-45-67",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    trace = client.get(f"/v1/traces/{payload['trace_id']}")
    assert trace.status_code == 200
    assert "[PHONE]" in trace.json()["redacted_message"]
    assert "+7 999" not in trace.json()["redacted_message"]
