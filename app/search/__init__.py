"""Catalog search services."""

from app.models.document import Perfume
from app.indexer.inverted_index import InvertedIndex, normalize_text
from app.search.ranker import rank


class CatalogSearch:
    """Provides basic name search and advanced product filters."""

    def __init__(self, perfumes: list[Perfume]) -> None:
        self._perfumes = list(perfumes)
        self._index = InvertedIndex(self._perfumes)

    def basic_search(self, query: str) -> list[Perfume]:
        if not query.strip():
            return []
        return rank(self._index.find(query), query)

    def advanced_search(
        self,
        query: str = "",
        brand: str = "",
        gender: str = "",
        family: str = "",
        min_price: float | None = None,
        max_price: float | None = None,
        presentation_ml: int | None = None,
        in_stock: bool = False,
    ) -> list[Perfume]:
        candidates = self.basic_search(query) if query.strip() else list(self._perfumes)
        filters = (
            (brand, lambda perfume: normalize_text(perfume.brand) == normalize_text(brand)),
            (gender, lambda perfume: normalize_text(perfume.gender) == normalize_text(gender)),
            (family, lambda perfume: normalize_text(perfume.family) == normalize_text(family)),
        )
        for value, predicate in filters:
            if value:
                candidates = [perfume for perfume in candidates if predicate(perfume)]
        if min_price is not None:
            candidates = [perfume for perfume in candidates if perfume.price >= min_price]
        if max_price is not None:
            candidates = [perfume for perfume in candidates if perfume.price <= max_price]
        if presentation_ml is not None:
            candidates = [perfume for perfume in candidates if perfume.presentation_ml == presentation_ml]
        if in_stock:
            candidates = [perfume for perfume in candidates if perfume.stock > 0]
        return candidates


__all__ = ["CatalogSearch", "Perfume"]
