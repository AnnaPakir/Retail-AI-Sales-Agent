from __future__ import annotations

from .catalog import Catalog


class ProductTools:
    """Typed business tools. The agent never receives raw SQL access."""

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    def get_price(self, product_id: str) -> dict[str, object]:
        product = self.catalog.by_id(product_id)
        if product is None:
            return {"found": False, "product_id": product_id}
        return {
            "found": True,
            "product_id": product.id,
            "product_name": product.name,
            "price_rub": product.price_rub,
            "currency": "RUB",
        }

    def check_stock(self, product_id: str) -> dict[str, object]:
        product = self.catalog.by_id(product_id)
        if product is None:
            return {"found": False, "product_id": product_id}
        return {
            "found": True,
            "product_id": product.id,
            "product_name": product.name,
            "available": product.available,
        }
