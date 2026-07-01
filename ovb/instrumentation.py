"""Instrumentation shared by both engines: a per-call recorder plus an
append-only (WORM) event log. This is what turns the demo into a *measurement*
instead of an assertion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .llm import Usage


@dataclass
class Call:
    """One agent invocation."""

    seq: int
    engine: str
    agent: str
    usage: Usage
    latency_ms: float
    changed: bool
    writes: dict            # field -> new value
    trigger: str = ""       # what caused this call (e.g. 'scope changed', 'sweep 2')


@dataclass
class Event:
    """One write to the shared state — the WORM audit record."""

    seq: int
    agent: str
    field: str
    old: Any
    new: Any


class Recorder:
    """Collects per-call metrics and the write log for one engine run."""

    def __init__(self, engine: str):
        self.engine = engine
        self.calls: list[Call] = []
        self.events: list[Event] = []   # WORM log of state writes
        self._seq = 0
        self._eseq = 0

    def record_call(self, agent: str, usage: Usage, latency_ms: float,
                    writes: dict, trigger: str = "") -> None:
        self._seq += 1
        self.calls.append(
            Call(
                seq=self._seq, engine=self.engine, agent=agent, usage=usage,
                latency_ms=latency_ms, changed=bool(writes), writes=dict(writes),
                trigger=trigger,
            )
        )

    def record_write(self, agent: str, field_name: str, old: Any, new: Any) -> None:
        self._eseq += 1
        self.events.append(Event(self._eseq, agent, field_name, old, new))

    # ---- aggregates -------------------------------------------------------
    @property
    def n_calls(self) -> int:
        return len(self.calls)

    @property
    def n_effective(self) -> int:
        """Calls that actually changed something (the rest are wasted turns)."""
        return sum(1 for c in self.calls if c.changed)

    @property
    def n_wasted(self) -> int:
        return self.n_calls - self.n_effective

    @property
    def total_usage(self) -> Usage:
        u = Usage()
        for c in self.calls:
            u = u + c.usage
        return u

    @property
    def total_latency_ms(self) -> float:
        return sum(c.latency_ms for c in self.calls)

    @property
    def n_writes(self) -> int:
        return len(self.events)


def latency_for(usage: Usage, real: bool, measured_ms: float) -> float:
    """Real runs report wall-clock; mock runs synthesize a reproducible value
    proportional to tokens moved (no clocks, so results never flake)."""
    return measured_ms if real else usage.total / 10.0
