from sales_agent.agent import SalesAgent
from sales_agent.schemas import Action, ChatRequest, Intent


def test_price_comes_from_typed_tool() -> None:
    result = SalesAgent().handle(ChatRequest(session_id="price", message="Сколько стоит A101?"))
    assert result.intent is Intent.PRICE
    assert result.action is Action.ANSWER
    assert result.tool_calls[0].name == "get_price"
    assert result.tool_calls[0].arguments == {"product_id": "NW-A101"}


def test_purchase_intent_requires_explicit_handoff_confirmation() -> None:
    agent = SalesAgent()
    first = agent.handle(ChatRequest(session_id="sale", message="Хочу купить D210"))
    second = agent.handle(ChatRequest(session_id="sale", message="Да, передайте оператору"))
    assert first.action is Action.ASK_CONFIRMATION
    assert second.action is Action.HUMAN_HANDOFF
    assert second.intent is Intent.PURCHASE_CONFIRMATION


def test_thanks_does_not_confirm_handoff() -> None:
    agent = SalesAgent()
    agent.handle(ChatRequest(session_id="close", message="Хочу купить D210"))
    result = agent.handle(ChatRequest(session_id="close", message="Спасибо"))
    assert result.intent is Intent.CLOSING
    assert result.action is Action.END_DIALOGUE


def test_unknown_product_is_not_guessed() -> None:
    result = SalesAgent().handle(ChatRequest(session_id="unknown", message="Цена модели X999?"))
    assert result.intent is Intent.AMBIGUOUS
    assert result.tool_calls == []


def test_request_id_is_idempotent() -> None:
    agent = SalesAgent()
    request = ChatRequest(
        session_id="duplicate",
        request_id="crm-event-42",
        message="Сколько стоит A101?",
    )
    first = agent.handle(request)
    second = agent.handle(request)
    assert second.trace_id == first.trace_id
    assert second == first


def test_existing_order_is_handed_to_human() -> None:
    result = SalesAgent().handle(ChatRequest(session_id="order", message="Где мой заказ №123456?"))
    assert result.intent is Intent.EXISTING_ORDER
    assert result.action is Action.HUMAN_HANDOFF
