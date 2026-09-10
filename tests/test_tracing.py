from sales_agent.tracing import redact_personal_data


def test_trace_redacts_phone_email_and_order_id() -> None:
    text = "Заказ №123456, +7 (999) 111-22-33, ivan@example.com"
    redacted = redact_personal_data(text)
    assert "123456" not in redacted
    assert "999" not in redacted
    assert "ivan@example.com" not in redacted
    assert "[ORDER_ID]" in redacted
    assert "[PHONE]" in redacted
    assert "[EMAIL]" in redacted
