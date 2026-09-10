from __future__ import annotations

import re
from dataclasses import dataclass

from .schemas import Intent


@dataclass(frozen=True)
class Route:
    intent: Intent
    reason: str


def _has(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def route_message(message: str, *, awaiting_confirmation: bool = False) -> Route:
    text = " ".join(message.casefold().split())

    explicit_confirmation = bool(
        re.fullmatch(r"(?:да|беру|согласен|согласна)[.!]?", text)
        or _has(text, ("да, оформ", "да оформ", "оформляем", "оформляйте"))
    )
    if awaiting_confirmation and explicit_confirmation:
        return Route(Intent.PURCHASE_CONFIRMATION, "confirmation after explicit sales CTA")

    if _has(text, ("ты бот", "вы бот", "искусственный интеллект", "нейросеть")):
        return Route(Intent.TRANSPARENCY, "customer asked who they are speaking with")

    if _has(text, ("оператор", "позови человека", "менеджер", "живой сотрудник")):
        return Route(Intent.HUMAN_REQUEST, "customer explicitly requested a person")

    if _has(
        text,
        (
            "мой заказ",
            "заказ №",
            "заказ #",
            "где заказ",
            "не пришёл",
            "не пришел",
            "едет вечность",
            "задержка доставки",
        ),
    ):
        return Route(Intent.EXISTING_ORDER, "question concerns an existing order")

    if _has(
        text,
        ("сломал", "сломалась", "сломались", "не работает", "ремонт моего", "гарантийный случай"),
    ):
        return Route(Intent.REPAIR, "individual repair or warranty case")

    if _has(text, ("оптом", "оптов", "партия для магазина", "дилер")):
        return Route(Intent.WHOLESALE, "wholesale terms require a commercial owner")

    if _has(text, ("скидк", "льгот", "ветеран", "промокод")):
        return Route(Intent.DISCOUNT, "individual discount is not decided by the model")

    if _has(text, ("запчаст", "деталь отдельно", "механизм отдельно")):
        return Route(Intent.SPARE_PARTS, "spare-parts availability requires an operator")

    if _has(text, ("пришли фото", "отправь фото", "покажи все модели", "покажи фотографии")):
        return Route(Intent.UNSUPPORTED_ACTION, "channel cannot reliably send a gallery")

    if _has(text, ("спасибо", "понятно, спасибо", "до свидания", "всего доброго")) or re.fullmatch(
        r"[\s👍🙏🙂😊❤️❤]+", message
    ):
        return Route(Intent.CLOSING, "polite closing is not a sales confirmation")

    purchase = _has(
        text, ("хочу купить", "готов купить", "беру ", "заказать эту", "оформить покупку")
    )
    if purchase:
        return Route(Intent.PURCHASE, "explicit intent to buy a concrete product")

    if _has(text, ("в наличии", "наличие", "остал")):
        return Route(Intent.STOCK, "stock question")

    if _has(text, ("цена", "сколько стоит", "стоимость")):
        return Route(Intent.PRICE, "price question")

    tokens = re.findall(r"[\w-]+", text, flags=re.UNICODE)
    if len(tokens) <= 3 and not _has(
        text, ("доставка", "гарантия", "магазин", "ремонт", "браслет", "механизм")
    ):
        return Route(Intent.AMBIGUOUS, "too little reliable context")

    return Route(Intent.CONSULTATION, "general product or policy consultation")
