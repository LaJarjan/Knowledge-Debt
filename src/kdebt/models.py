"""Small, serializable contracts shared by all product entry points."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Fact:
    id: str
    text: str
    line: int
    source: str


@dataclass(frozen=True)
class Concept:
    id: str
    path: str
    symbol: str
    kind: str
    line: int
    end_line: int
    fingerprint: str
    question: str
    facts: tuple[Fact, ...]
    caveat: str

    def to_dict(self) -> dict:
        return asdict(self)
