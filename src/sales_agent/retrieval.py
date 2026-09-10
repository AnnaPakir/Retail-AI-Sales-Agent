from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from .catalog import DATA_DIR


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zа-яё0-9-]+", text.casefold())


def _vector(text: str, dimensions: int = 64) -> list[float]:
    """Small deterministic embedding used only by the offline public demo."""
    result = [0.0] * dimensions
    for token in _tokens(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        result[index] += sign
    norm = math.sqrt(sum(value * value for value in result)) or 1.0
    return [value / norm for value in result]


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    text: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class SearchHit:
    document: Document
    score: float


class HybridRetriever:
    """Portable demo of lexical + vector score fusion.

    Production used PostgreSQL full-text search and pgvector. This version is
    deterministic and has no external model dependency, which keeps tests honest.
    """

    def __init__(self, data_path: Path | None = None) -> None:
        path = data_path or DATA_DIR / "knowledge_base.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.documents = [
            Document(
                id=item["id"],
                title=item["title"],
                text=item["text"],
                keywords=tuple(item.get("keywords", [])),
            )
            for item in payload
        ]
        self._vectors = {
            doc.id: _vector(f"{doc.title} {doc.text} {' '.join(doc.keywords)}")
            for doc in self.documents
        }

    def search(self, query: str, *, limit: int = 3) -> list[SearchHit]:
        query_tokens = set(_tokens(query))
        query_vector = _vector(query)
        hits: list[SearchHit] = []
        for document in self.documents:
            doc_tokens = set(
                _tokens(f"{document.title} {document.text} {' '.join(document.keywords)}")
            )
            lexical = len(query_tokens & doc_tokens) / max(len(query_tokens), 1)
            dense = max(_cosine(query_vector, self._vectors[document.id]), 0.0)
            score = 0.65 * lexical + 0.35 * dense
            if score > 0:
                hits.append(SearchHit(document=document, score=score))
        return sorted(hits, key=lambda item: item.score, reverse=True)[:limit]
