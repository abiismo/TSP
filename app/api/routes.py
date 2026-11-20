"""Framework-independent handlers used by the HTTP layer."""

from typing import Any

from app.search import CatalogSearch


def basic_search(search: CatalogSearch, query: str) -> list[dict[str, Any]]:
    return [perfume.to_dict() for perfume in search.basic_search(query)]


def advanced_search(search: CatalogSearch, params: dict[str, str]) -> list[dict[str, Any]]:
    min_price = float(params["min_price"]) if params.get("min_price") else None
    max_price = float(params["max_price"]) if params.get("max_price") else None
    presentation_ml = int(params["presentation_ml"]) if params.get("presentation_ml") else None
    in_stock = params.get("in_stock", "false").casefold() in {"1", "true", "yes"}
    return [
        perfume.to_dict()
        for perfume in search.advanced_search(
            query=params.get("q", ""),
            brand=params.get("brand", ""),
            gender=params.get("gender", ""),
            family=params.get("family", ""),
            min_price=min_price,
            max_price=max_price,
            presentation_ml=presentation_ml,
            in_stock=in_stock,
        )
    ]
