"""Relevance scoring for catalog search results."""

from app.indexer.inverted_index import normalize_text, tokenize
from app.models.document import Perfume


def rank(perfumes: list[Perfume], query: str) -> list[Perfume]:
    terms = tokenize(query)
    if not terms:
        return sorted(perfumes, key=lambda perfume: normalize_text(perfume.name))

    weights = (("name", 5), ("brand", 3), ("family", 2), ("description", 1))

    def score(perfume: Perfume) -> tuple[int, str]:
        total = 0
        for field, weight in weights:
            text = normalize_text(getattr(perfume, field))
            field_tokens = set(text.split())
            total += sum(weight for term in terms if term in field_tokens)
            if field == "name" and all(term in field_tokens for term in terms):
                total += 4
            if field == "name" and text.startswith(normalize_text(query)):
                total += 3
        return -total, normalize_text(perfume.name)

    return sorted(perfumes, key=score)
