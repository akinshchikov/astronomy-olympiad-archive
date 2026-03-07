from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class SeedRequest:
    source_id: str
    url: str
    olympiad_family: str
    source_role: str
    source_priority: int
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceDefinition:
    source_id: str
    label: str
    olympiad_family: str
    source_role: str
    source_priority: int
    strategy: str
    seed_urls: list[str] = field(default_factory=list)
    notes: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

