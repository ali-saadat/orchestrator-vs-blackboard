"""Scenario — build a gaming PC that fits a budget.

Four specialists agree on one build:
  - GPU        = the graphics card tier (1–4). You want the top tier.
  - Budget     = the money; a hard cap. Cost = tier × $/tier, so a higher tier
                 may not fit — Budget then caps the tier you can afford.
  - Power      = the PSU wattage; it scales with the GPU tier.
  - Performance= the FPS class; it follows the GPU tier.

Interdependence (why the shared board helps): the GPU tier drives everything.
Dropping it to fit the budget also lowers the wattage and the FPS class, so a
change ripples — but only to the agents that depend on the tier. The tightly
coupled pair is GPU ↔ Budget (want-vs-afford); Power and Performance just follow.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core.state import PlanState

# defaults (used when no ScenarioParams is supplied)
GPU_PRICE = 300          # $ per GPU tier
BUDGET_CAP = 1000        # $ hard cap
WATTS_PER_TIER = 150     # PSU watts added per tier
WATTS_BASE = 100         # PSU baseline watts
TOP_TIER = 4             # highest GPU tier on offer


@dataclass(frozen=True)
class ScenarioParams:
    wanted_gpu: int = TOP_TIER      # the tier you'd like (the "ask")
    budget_cap: int = BUDGET_CAP    # the hard $ cap
    gpu_price: int = GPU_PRICE
    watts_per_tier: int = WATTS_PER_TIER
    watts_base: int = WATTS_BASE


def _p(params: "ScenarioParams | None") -> ScenarioParams:
    return params or ScenarioParams()


def scenario_text(params: "ScenarioParams | None" = None) -> str:
    p = _p(params)
    return (
        f"Build a gaming PC. You want a tier-{p.wanted_gpu} GPU, but there is a hard "
        f"budget cap of ${p.budget_cap} (each GPU tier costs ${p.gpu_price}); the PSU "
        f"wattage and the FPS class both follow the GPU tier. GPU, Budget, Power and "
        "Performance are interdependent — find the best build that fits the budget."
    )


# kept for imports/back-compat
SCENARIO = scenario_text()


def initial_state(params: "ScenarioParams | None" = None) -> PlanState:
    return PlanState(gpu=_p(params).wanted_gpu)


def perf_for(gpu):
    """FPS class that follows the GPU tier."""
    if gpu is None:
        return None
    if gpu >= 4:
        return "ultra"
    if gpu == 3:
        return "high"
    if gpu == 2:
        return "medium"
    return "low"


def watts_for(gpu, params: "ScenarioParams | None" = None):
    p = _p(params)
    return None if gpu is None else gpu * p.watts_per_tier + p.watts_base


def is_consistent(state: PlanState, params: "ScenarioParams | None" = None) -> bool:
    """The gate: is this a valid, self-consistent build?"""
    p = _p(params)
    g = state.gpu
    return all(
        [
            state.cost is not None and state.cost <= p.budget_cap,
            state.max_gpu is not None and g <= state.max_gpu,
            state.watts == watts_for(g, p),
            state.perf == perf_for(g),
        ]
    )
