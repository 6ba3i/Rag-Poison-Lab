from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TraceDocItem:
    movie_id: int
    title: str
    snippet: str
    poison_marker: bool
    poison_payload: str
    has_poison: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "movie_id": self.movie_id,
            "title": self.title,
            "snippet": self.snippet,
            "poison_marker": self.poison_marker,
            "poison_payload": self.poison_payload,
            "has_poison": self.has_poison,
        }
