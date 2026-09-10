from sales_agent.llm import OpenAICompatibleGenerator


def test_numeric_guard_rejects_ungrounded_numbers() -> None:
    assert (
        OpenAICompatibleGenerator._numbers_are_grounded(
            "Цена 18 900 рублей, гарантия 2 года.",
            "Цена 18 900 рублей.",
        )
        is False
    )


def test_numeric_guard_accepts_numbers_from_context() -> None:
    assert (
        OpenAICompatibleGenerator._numbers_are_grounded(
            "Водозащита — 200 метров.",
            "Модель имеет водозащиту 200 метров.",
        )
        is True
    )
