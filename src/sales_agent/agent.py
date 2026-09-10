from __future__ import annotations

from threading import Lock
from uuid import uuid4

from .catalog import Catalog, Product
from .llm import GroundedGenerator, generator_from_environment
from .retrieval import HybridRetriever
from .router import route_message
from .schemas import (
    Action,
    ChatRequest,
    ChatResponse,
    ExecutionTrace,
    Intent,
    SourceRef,
    ToolCall,
    TraceEvent,
)
from .state import DialogStateStore
from .tools import ProductTools
from .tracing import TraceStore, redact_personal_data


class SalesAgent:
    def __init__(self, generator: GroundedGenerator | None = None) -> None:
        self.catalog = Catalog()
        self.retriever = HybridRetriever()
        self.tools = ProductTools(self.catalog)
        self.generator = generator or generator_from_environment()
        self.states = DialogStateStore()
        self.traces = TraceStore()
        self._idempotency: dict[tuple[str, str], ChatResponse] = {}
        self._cache_lock = Lock()

    def handle(self, request: ChatRequest) -> ChatResponse:
        if request.request_id:
            cache_key = (request.session_id, request.request_id)
            with self._cache_lock:
                cached = self._idempotency.get(cache_key)
            if cached is not None:
                return cached

        state = self.states.get(request.session_id)
        trace_id = str(uuid4())
        trace = ExecutionTrace(
            trace_id=trace_id,
            session_id=request.session_id,
            request_id=request.request_id,
            redacted_message=redact_personal_data(request.message),
        )
        route = route_message(
            request.message,
            awaiting_confirmation=state.pending_product_id is not None,
        )
        trace.events.append(
            TraceEvent(step="route", data={"intent": route.intent.value, "reason": route.reason})
        )

        product = self.catalog.resolve(request.message)
        if product:
            trace.events.append(
                TraceEvent(step="entity_resolution", data={"product_id": product.id})
            )

        response = self._execute(request, route.intent, product, trace)
        self.traces.save(trace)

        if request.request_id:
            cache_key = (request.session_id, request.request_id)
            with self._cache_lock:
                self._idempotency[cache_key] = response
        return response

    def _execute(
        self,
        request: ChatRequest,
        intent: Intent,
        product: Product | None,
        trace: ExecutionTrace,
    ) -> ChatResponse:
        if intent in {
            Intent.HUMAN_REQUEST,
            Intent.EXISTING_ORDER,
            Intent.REPAIR,
            Intent.WHOLESALE,
            Intent.DISCOUNT,
            Intent.SPARE_PARTS,
        }:
            reasons = {
                Intent.HUMAN_REQUEST: "Вы попросили подключить сотрудника.",
                Intent.EXISTING_ORDER: "По действующему заказу нужен доступ сотрудника к CRM.",
                Intent.REPAIR: "Индивидуальный случай ремонта должен проверить специалист.",
                Intent.WHOLESALE: "Условия оптовой продажи согласует коммерческий отдел.",
                Intent.DISCOUNT: "Индивидуальные условия подтверждает сотрудник.",
                Intent.SPARE_PARTS: "Наличие отдельной детали должен подтвердить специалист.",
            }
            self.states.clear(request.session_id)
            return self._response(
                trace,
                intent,
                Action.HUMAN_HANDOFF,
                f"{reasons[intent]} Передам вопрос специалисту вместе с контекстом.",
            )

        if intent is Intent.PURCHASE_CONFIRMATION:
            state = self.states.get(request.session_id)
            selected = self.catalog.by_id(state.pending_product_id or "")
            self.states.clear(request.session_id)
            if selected is None:
                return self._response(
                    trace,
                    Intent.AMBIGUOUS,
                    Action.ASK_CLARIFICATION,
                    "Уточните, пожалуйста, какую модель вы рассматриваете.",
                )
            trace.events.append(
                TraceEvent(
                    step="handoff", data={"product_id": selected.id, "reason": "purchase_confirmed"}
                )
            )
            return self._response(
                trace,
                intent,
                Action.HUMAN_HANDOFF,
                (
                    f"Передам вопрос специалисту по {selected.name}. "
                    "Он уточнит детали и поможет с оформлением."
                ),
            )

        if intent is Intent.TRANSPARENCY:
            return self._response(
                trace,
                intent,
                Action.ANSWER,
                (
                    "Да, я ИИ-консультант. Отвечаю по каталогу и правилам магазина. "
                    "Если вопрос требует решения сотрудника, я передам его специалисту."
                ),
            )

        if intent is Intent.CLOSING:
            self.states.clear(request.session_id)
            return self._response(
                trace,
                intent,
                Action.END_DIALOGUE,
                "Спасибо за обращение! Если появятся вопросы, напишите — постараюсь помочь.",
            )

        if intent is Intent.UNSUPPORTED_ACTION:
            return self._response(
                trace,
                intent,
                Action.ASK_CLARIFICATION,
                (
                    "Я не могу надёжно отправить всю фотогалерею в этом канале. "
                    "Могу дать ссылку на каталог или помочь подобрать модель "
                    "по материалу, размеру и бюджету."
                ),
            )

        if intent is Intent.AMBIGUOUS:
            return self._response(
                trace,
                intent,
                Action.ASK_CLARIFICATION,
                "Не хочу угадывать. Уточните, пожалуйста, название модели или сам вопрос.",
            )

        if intent in {Intent.PRICE, Intent.STOCK, Intent.PURCHASE} and product is None:
            return self._response(
                trace,
                Intent.AMBIGUOUS,
                Action.ASK_CLARIFICATION,
                (
                    "Уточните название или артикул модели — без этого я не буду "
                    "угадывать цену и наличие."
                ),
            )

        if intent is Intent.PRICE and product:
            call = self._tool_call("get_price", product)
            trace.events.append(TraceEvent(step="tool", data=call.model_dump()))
            return self._response(
                trace,
                intent,
                Action.ANSWER,
                f"{product.name} стоит {product.price_rub:,} ₽.".replace(",", " "),
                tool_calls=[call],
            )

        if intent is Intent.STOCK and product:
            call = self._tool_call("check_stock", product)
            trace.events.append(TraceEvent(step="tool", data=call.model_dump()))
            text = (
                f"{product.name} сейчас есть в наличии."
                if product.available
                else f"{product.name} сейчас нет в наличии. Могу помочь подобрать альтернативу."
            )
            return self._response(trace, intent, Action.ANSWER, text, tool_calls=[call])

        if intent is Intent.PURCHASE and product:
            price_call = self._tool_call("get_price", product)
            stock_call = self._tool_call("check_stock", product)
            for call in (price_call, stock_call):
                trace.events.append(TraceEvent(step="tool", data=call.model_dump()))
            if not product.available:
                return self._response(
                    trace,
                    intent,
                    Action.ANSWER,
                    f"{product.name} сейчас нет в наличии. Могу помочь подобрать похожую модель.",
                    tool_calls=[price_call, stock_call],
                )
            self.states.get(request.session_id).pending_product_id = product.id
            delivery_note = ""
            sources: list[SourceRef] = []
            if "достав" in request.message.casefold():
                delivery_hits = self.retriever.search("доставка")
                if delivery_hits:
                    delivery_note = f" {delivery_hits[0].document.text}"
                    sources = [
                        SourceRef(
                            id=delivery_hits[0].document.id, title=delivery_hits[0].document.title
                        )
                    ]
            price = f"{product.price_rub:,}".replace(",", " ")
            return self._response(
                trace,
                intent,
                Action.ASK_CONFIRMATION,
                (
                    f"{product.name} есть в наличии, цена — {price} ₽.{delivery_note} "
                    "Могу передать вопрос специалисту: он уточнит детали и поможет с оформлением."
                ),
                sources=sources,
                tool_calls=[price_call, stock_call],
            )

        return self._consult(request, product, trace)

    def _consult(
        self,
        request: ChatRequest,
        product: Product | None,
        trace: ExecutionTrace,
    ) -> ChatResponse:
        hits = self.retriever.search(request.message)
        trace.events.append(
            TraceEvent(
                step="retrieval",
                data={
                    "hits": [{"id": hit.document.id, "score": round(hit.score, 4)} for hit in hits]
                },
            )
        )
        if product:
            context = f"{product.name}: {product.description}"
            if hits and hits[0].score >= 0.18:
                context = f"{context} {hits[0].document.text}"
            generation = self.generator.generate(question=request.message, context=context)
            trace.events.append(
                TraceEvent(
                    step="generation",
                    data={
                        "provider": generation.provider,
                        "used_fallback": generation.used_fallback,
                    },
                )
            )
            return self._response(
                trace,
                Intent.CONSULTATION,
                Action.ANSWER,
                generation.text,
                sources=[
                    SourceRef(id=hit.document.id, title=hit.document.title) for hit in hits[:1]
                ],
            )
        if not hits or hits[0].score < 0.18:
            return self._response(
                trace,
                Intent.AMBIGUOUS,
                Action.ASK_CLARIFICATION,
                (
                    "В базе знаний нет надёжного ответа. Уточните вопрос, и я попробую "
                    "найти точную информацию или подключу сотрудника."
                ),
            )
        best = hits[0].document
        generation = self.generator.generate(question=request.message, context=best.text)
        trace.events.append(
            TraceEvent(
                step="generation",
                data={
                    "provider": generation.provider,
                    "used_fallback": generation.used_fallback,
                },
            )
        )
        return self._response(
            trace,
            Intent.CONSULTATION,
            Action.ANSWER,
            generation.text,
            sources=[SourceRef(id=best.id, title=best.title)],
        )

    def _tool_call(self, name: str, product: Product) -> ToolCall:
        result = (
            self.tools.get_price(product.id)
            if name == "get_price"
            else self.tools.check_stock(product.id)
        )
        return ToolCall(name=name, arguments={"product_id": product.id}, result=result)

    @staticmethod
    def _response(
        trace: ExecutionTrace,
        intent: Intent,
        action: Action,
        text: str,
        *,
        sources: list[SourceRef] | None = None,
        tool_calls: list[ToolCall] | None = None,
    ) -> ChatResponse:
        trace.events.append(TraceEvent(step="policy", data={"action": action.value}))
        return ChatResponse(
            trace_id=trace.trace_id,
            intent=intent,
            action=action,
            response=text,
            sources=sources or [],
            tool_calls=tool_calls or [],
        )
