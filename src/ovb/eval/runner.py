"""Run harness: build the shared world once, run each topology over it.

The world (registry, gate, initial state, LLM, config, scenario params) is
constructed ONCE and handed identically to every engine — the fairness guarantee
in code. `event_sink`, when supplied, receives every event as it is emitted (used
by the live server to stream in real time).
"""
from __future__ import annotations

from ..config import RunConfig
from ..contracts import EngineResult, Sequencer
from ..core.gate import PredicateGate
from ..core.llm import CassetteLLM, ClaudeLLM, MockLLM
from ..domain import agents, task
from ..domain.task import ScenarioParams
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


def build_gate(params: ScenarioParams) -> PredicateGate:
    return PredicateGate(
        lambda s: task.is_consistent(s, params),
        spec=f"party/v1/cap={params.budget_cap}/price={params.price_per_guest}",
    )


async def run_engine(name: str, config: RunConfig,
                     params: "ScenarioParams | None" = None,
                     event_sink=None) -> EngineResult:
    p = params or ScenarioParams()
    engine = ENGINES[name](
        registry=agents.build_registry(p), gate=build_gate(p),
        initial_state=task.initial_state(p), llm=_make_llm(config), config=config,
        run_id=name, sequencer=Sequencer(), scenario=task.scenario_text(p),
        event_sink=event_sink,
    )
    return await engine.run()


async def run_all(config: RunConfig,
                  params: "ScenarioParams | None" = None) -> dict[str, EngineResult]:
    """Run all three topologies over the identical world."""
    return {name: await run_engine(name, config, params) for name in ENGINES}
