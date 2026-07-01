"""Run harness: build the shared world once, run each topology over it.

The world (registry, gate, initial state, LLM, config) is constructed ONCE and
handed identically to every engine — that is the fairness guarantee in code. Each
engine gets its own `Sequencer`-backed recorder but the same everything-else.
"""
from __future__ import annotations

from ..config import RunConfig
from ..contracts import EngineResult, Sequencer
from ..core.gate import PredicateGate
from ..core.llm import CassetteLLM, ClaudeLLM, MockLLM
from ..domain import agents, task
from ..engines import ENGINES


def _make_llm(config: RunConfig):
    base = (ClaudeLLM if config.real else MockLLM)(
        model=config.model, temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    if config.cassette:
        mode = "record" if config.real else "replay"
        return CassetteLLM(base, config.cassette, mode=mode, model=config.model,
                           temperature=config.temperature,
                           max_tokens=config.max_tokens)
    return base


async def run_engine(name: str, config: RunConfig) -> EngineResult:
    registry = agents.build_registry()
    gate = PredicateGate(task.is_consistent, spec="reconcile.is_consistent/v1")
    llm = _make_llm(config)
    engine = ENGINES[name](
        registry=registry, gate=gate, initial_state=task.initial_state(),
        llm=llm, config=config, run_id=f"{name}", sequencer=Sequencer(),
        scenario=task.SCENARIO,
    )
    return await engine.run()


async def run_all(config: RunConfig) -> dict[str, EngineResult]:
    """Run all three topologies over the identical world."""
    results: dict[str, EngineResult] = {}
    for name in ENGINES:
        results[name] = await run_engine(name, config)
    return results
