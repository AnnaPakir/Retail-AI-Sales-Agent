from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PROJECT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PACKAGE_DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR = PROJECT_DATA_DIR if PROJECT_DATA_DIR.exists() else PACKAGE_DATA_DIR


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    aliases: tuple[str, ...]
    description: str
    price_rub: int
    available: bool


class Catalog:
    def __init__(self, data_path: Path | None = None) -> None:
        path = data_path or DATA_DIR / "products.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.products = [
            Product(
                id=item["id"],
                name=item["name"],
                aliases=tuple(item["aliases"]),
                description=item["description"],
                price_rub=item["price_rub"],
                available=item["available"],
            )
            for item in payload
        ]

    def resolve(self, text: str) -> Product | None:
        normalized = text.casefold()
        matches: list[tuple[int, Product]] = []
        for product in self.products:
            candidates = (product.id, product.name, *product.aliases)
            for candidate in candidates:
                if candidate.casefold() in normalized:
                    matches.append((len(candidate), product))
        return max(matches, key=lambda item: item[0])[1] if matches else None

    def by_id(self, product_id: str) -> Product | None:
        return next((item for item in self.products if item.id == product_id), None)
