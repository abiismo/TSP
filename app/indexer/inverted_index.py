"""Small in-memory inverted index for the demo catalog."""

import re
import unicodedata
from collections import defaultdict
from typing import Iterable

from app.models.document import Perfume


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", without_accents).strip()


def tokenize(value: str) -> list[str]:
    return normalize_text(value).split()


class InvertedIndex:
    def __init__(self, perfumes: Iterable[Perfume]) -> None:
        self._postings: dict[str, set[str]] = defaultdict(set)
        self._perfumes: dict[str, Perfume] = {}
        for perfume in perfumes:
            self.add(perfume)

    def add(self, perfume: Perfume) -> None:
        self._perfumes[perfume.id] = perfume
        # Basic search is intentionally restricted to product names. The
        # advanced search handles the structured attributes as filters.
        for token in set(tokenize(perfume.name)):
            self._postings[token].add(perfume.id)

    def find(self, query: str) -> list[Perfume]:
        terms = tokenize(query)
        if not terms:
            return []
        found_ids: set[str] = set()
        for term in terms:
            found_ids.update(self._postings.get(term, set()))
        return [self._perfumes[perfume_id] for perfume_id in found_ids]
