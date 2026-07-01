"""Canonical, load-bearing contracts — the single source of truth.

Everything else imports these types rather than re-declaring them. Per the plan's
Phase 0, this file is what stops the codebase from drifting into five subtly
different `Usage` shapes or event envelopes. If you change a shape here, you
change it everywhere.

Event field names deliberately track OpenTelemetry GenAI semantic conventions
(`gen_ai.*`) so an OTLP exporter is a mechanical rename (see docs/HARNESS.md).
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------- token usage
class Usage(BaseModel):
    """The real Anthropic cost vector. Cache buckets are billed at different
    rates than fresh input (see pricing.py)."""

    model_config = ConfigDict(frozen=True)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
        )

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens
            + other.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens
            + other.cache_read_input_tokens,
        )

    def cost_usd(self, price: "ModelPrice") -> float:
        m = 1_000_000
        return (
            self.input_tokens / m * price.input_per_mtok
            + self.output_tokens / m * price.output_per_mtok
            + self.cache_creation_input_tokens / m * price.cache_write_per_mtok
            + self.cache_read_input_tokens / m * price.cache_read_per_mtok
        )


class ModelPrice(BaseModel):
    model_config = ConfigDict(frozen=True)
    model: str
    input_per_mtok: float
    output_per_mtok: float
    cache_write_per_mtok: float
    cache_read_per_mtok: float


class Completion(BaseModel):
    """What an LLM client returns."""

    model_config = ConfigDict(frozen=True)
    text: str
    usage: Usage = Usage()


class ActResult(BaseModel):
    """What a KnowledgeSource returns from `act`: the validated patch (the rule's
    numeric decision), the model's narration, and real token usage."""

    model_config = ConfigDict(frozen=True)
    source: str
    patch: dict[str, Any]
    rationale: str
    usage: Usage = Usage()


# ---------------------------------------------------------------- WORM events
# One flat, ordered event stream. `kind` is our event name; `attrs` are the
# OTel-style attributes. Engines emit these; CLI, benchmark, viz, and OTLP
# export all consume them.
class Event(BaseModel):
    model_config = ConfigDict(frozen=True)
    seq: int                       # monotonic, totally-ordered (WORM)
    run_id: str
    control_model: str             # orchestrator | blackboard | hybrid
    kind: str                      # run_started | agent_activated | llm_call_* | state_write | agent_retriggered | gate_checked | run_finished
    agent: str | None = None
    attrs: dict[str, Any] = Field(default_factory=dict)


class Sequencer:
    """The one monotonic clock. All engines share an instance so their WORM logs
    are totally ordered and directly comparable."""

    def __init__(self) -> None:
        self._n = 0

    def next(self) -> int:
        self._n += 1
        return self._n


# ---------------------------------------------------------------- engine iface
class EngineResult(BaseModel):
    """Uniform result the harness/UI treat identically across topologies."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    control_model: str
    state: dict[str, Any]
    consistent: bool
    steps: int                     # rounds (orchestrator) or event-loop steps
    recorder: Any                  # trace.Recorder (kept as Any to avoid a cycle)


@runtime_checkable
class Engine(Protocol):
    """Every topology implements this; that's why the harness runs them
    uniformly. The ONLY per-engine code is `run`'s scheduling."""

    control_model: str

    async def run(self) -> EngineResult: ...
