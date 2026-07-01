"""Scenario S1 — interdependent project-plan reconciliation.

An over-ambitious plan must be reconciled into a self-consistent state under
interdependent constraints: cutting scope to fit the budget shortens the
timeline, which lowers the risk. Chosen because interdependence is exactly where
the shared-state harness earns its keep.

The scenario is parameterized (`ScenarioParams`) so the *same prompt* — requested
features + budget cap — can be fed to all three harnesses from the live UI. The
module-level defaults keep the back-compatible `is_consistent(state)` /
`build_registry()` call sites working.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core.state import PlanState

# defaults (used when no ScenarioParams is supplied)
COST_PER_FEATURE_K = 15
BUDGET_CAP_K = 90
WEEKS_PER_FEATURE = 2
DEADLINE_WEEKS = 14


@dataclass(frozen=True)
class ScenarioParams:
    requested_features: int = 8
    budget_cap_k: int = BUDGET_CAP_K
    cost_per_feature_k: int = COST_PER_FEATURE_K
    weeks_per_feature: int = WEEKS_PER_FEATURE
    deadline_weeks: int = DEADLINE_WEEKS


def _p(params: "ScenarioParams | None") -> ScenarioParams:
    return params or ScenarioParams()


def scenario_text(params: "ScenarioParams | None" = None) -> str:
    p = _p(params)
    return (
        f"Reconcile a project plan. The team asked for {p.requested_features} "
        f"features, but there is a hard budget cap of ${p.budget_cap_k}k (each "
        f"feature costs ${p.cost_per_feature_k}k), a {p.weeks_per_feature}-week "
        f"build time per feature, and a {p.deadline_weeks}-week risk threshold. "
        "Scope, Budget, Timeline and Risk are interdependent."
    )


# kept for imports/back-compat
SCENARIO = scenario_text()


def initial_state(params: "ScenarioParams | None" = None) -> PlanState:
    return PlanState(scope=_p(params).requested_features)


def risk_for(scope, timeline, params: "ScenarioParams | None" = None):
    p = _p(params)
    if scope is None or timeline is None:
        return None
    if scope > 6 or timeline > p.deadline_weeks:
        return "high"
    if scope > 4:
        return "medium"
    return "low"


def is_consistent(state: PlanState, params: "ScenarioParams | None" = None) -> bool:
    """The gate predicate: is the plan self-consistent under every constraint?"""
    p = _p(params)
    s = state.scope
    return all(
        [
            state.budget_k is not None and state.budget_k <= p.budget_cap_k,
            state.max_scope is not None and s <= state.max_scope,
            state.timeline_weeks == s * p.weeks_per_feature,
            state.risk == risk_for(s, state.timeline_weeks, p),
        ]
    )
