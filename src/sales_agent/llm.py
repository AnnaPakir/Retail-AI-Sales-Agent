from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class Generation:
    text: str
    provider: str
    used_fallback: bool = False


class GroundedGenerator(Protocol):
    def generate(self, *, question: str, context: str) -> Generation: ...


class DeterministicGenerator:
    """Offline fallback: return the approved context without adding facts."""

    def generate(self, *, question: str, context: str) -> Generation:
        del question
        return Generation(text=context, provider="deterministic")


class OpenAICompatibleGenerator:
    """Optional adapter for OpenAI-compatible chat completion endpoints."""

    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.fallback = DeterministicGenerator()

    def generate(self, *, question: str, context: str) -> Generation:
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "temperature": 0.2,
                    "max_tokens": 350,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Ты консультант магазина. Ответь по-русски только по контексту. "
                                "Не добавляй цены, характеристики и обещания, которых нет в нём. "
                                "Если данных недостаточно, прямо скажи об этом."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Контекст:\n{context}\n\nВопрос:\n{question}",
                        },
                    ],
                },
                timeout=20.0,
            )
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"].strip()
            if not text or not self._numbers_are_grounded(text, context):
                fallback = self.fallback.generate(question=question, context=context)
                return Generation(
                    text=fallback.text,
                    provider=self.model,
                    used_fallback=True,
                )
            return Generation(text=text, provider=self.model)
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            fallback = self.fallback.generate(question=question, context=context)
            return Generation(text=fallback.text, provider=self.model, used_fallback=True)

    @staticmethod
    def _numbers_are_grounded(answer: str, context: str) -> bool:
        answer_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", answer))
        context_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", context))
        return answer_numbers <= context_numbers


def generator_from_environment() -> GroundedGenerator:
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    if all((base_url, api_key, model)):
        return OpenAICompatibleGenerator(base_url=base_url, api_key=api_key, model=model)
    return DeterministicGenerator()
