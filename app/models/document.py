"""Domain model for products indexed by the perfume catalog search."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Perfume:
    id: str
    name: str
    brand: str
    gender: str
    family: str
    price: float
    presentation_ml: int
    stock: int
    description: str = ""
    image_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
