"""Instrumentation: the WORM event stream + a per-call recorder.

`Recorder` owns both a structured `Call` list (for metrics/console) and the flat,
ordered `Event` stream (the WORM log the viz/UI/OTLP consume). Both engines share
a single `Sequencer`, so every event across every topology has a globally
monotonic `seq` — the logs are totally ordered and directly comparable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..contracts import Event, Sequencer, Usage
from ..pricing import get_price


@dataclass
class Call:
    seq: int
    control_model: str
    agent: str
    usage: Usage
    cost_usd: float
    latency_ms: float
    changed: bool
    writes: dict[str, Any]
    trigger: str


class Recorder:
    def __init__(self, control_model: str, run_id: str, sequencer: Sequencer,
                 model: str):
        self.control_model = control_model
        self.run_id = run_id
        self.seq = sequencer
        self.model = model
        self._price = get_price(model)
        self.calls: list[Call] = []
        self.events: list[Event] = []

    # ---- event emission (OTel-aligned kinds) --------------------------------
    def _emit(self, kind: str, agent: str | None = None, **attrs) -> Event:
        ev = Event(seq=self.seq.next(), run_id=self.run_id,
                   control_model=self.control_model, kind=kind, agent=agent,
                   attrs=attrs)
        self.events.append(ev)
        return ev

    def run_started(self, scenario: str) -> None:
        self._emit("run_started", scenario=scenario, model=self.model)

    def agent_activated(self, agent: str, trigger: str) -> None:
        self._emit("agent_activated", agent=agent, trigger=trigger)

    def llm_call_started(self, agent: str) -> None:
        self._emit("gen_ai.client.call.started", agent=agent)

    def call_finished(self, agent: str, usage: Usage, cost: float,
                      latency_ms: float, writes: dict, trigger: str) -> None:
        self.calls.append(Call(len(self.calls) + 1, self.control_model,
                               agent, usage, cost, latency_ms, bool(writes),
                               dict(writes), trigger))
        self._emit("gen_ai.client.call.finished", agent=agent,
                   **{"gen_ai.usage.input_tokens": usage.input_tokens,
                      "gen_ai.usage.output_tokens": usage.output_tokens,
                      "cache_read_input_tokens": usage.cache_read_input_tokens,
                      "cache_creation_input_tokens": usage.cache_creation_input_tokens,
                      "cost_usd": round(cost, 6), "latency_ms": round(latency_ms, 3),
                      "changed": bool(writes)})

    def state_write(self, agent: str, fieldname: str, old, new) -> None:
        self._emit("state_write", agent=agent, field=fieldname, old=old, new=new)

    def agent_retriggered(self, agent: str, because: str) -> None:
        self._emit("agent_retriggered", agent=agent, because=because)

    def gate_checked(self, passed: bool) -> None:
        self._emit("gate_checked", passed=passed)

    def run_finished(self, state: dict, consistent: bool) -> None:
        self._emit("run_finished", consistent=consistent, state=state,
                   **self.metrics())

    # ---- aggregates ---------------------------------------------------------
    @property
    def n_calls(self) -> int:
        return len(self.calls)

    @property
    def n_effective(self) -> int:
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
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def total_latency_ms(self) -> float:
        return sum(c.latency_ms for c in self.calls)

    @property
    def n_writes(self) -> int:
        return sum(1 for e in self.events if e.kind == "state_write")

    def metrics(self) -> dict:
        u = self.total_usage
        return {
            "calls": self.n_calls, "effective": self.n_effective,
            "wasted": self.n_wasted, "writes": self.n_writes,
            "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
            "cache_read_input_tokens": u.cache_read_input_tokens,
            "total_tokens": u.total, "cost_usd": round(self.total_cost_usd, 6),
            "latency_ms": round(self.total_latency_ms, 3),
        }

    # ---- export -------------------------------------------------------------
    def events_json(self) -> list[dict]:
        return [e.model_dump() for e in self.events]

    def write_jsonl(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w") as fh:
            for e in self.events:
                fh.write(json.dumps(e.model_dump()) + "\n")
