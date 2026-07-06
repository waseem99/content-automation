from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import DefaultDict

from pydantic import Field

from src.domain.base import FrozenRecord


class MetricSnapshot(FrozenRecord):
    counters: dict[str, int] = Field(default_factory=dict)
    totals: dict[str, str] = Field(default_factory=dict)


class MetricsRegistry:
    def __init__(self) -> None:
        self._counters: DefaultDict[str, int] = defaultdict(int)
        self._totals: DefaultDict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    def increment(self, name: str, value: int = 1) -> None:
        self._counters[name] += value

    def observe(self, name: str, value: Decimal | int | float | str) -> None:
        self._totals[name] += Decimal(str(value))

    def snapshot(self) -> MetricSnapshot:
        return MetricSnapshot(counters=dict(self._counters), totals={key: str(value) for key, value in self._totals.items()})
