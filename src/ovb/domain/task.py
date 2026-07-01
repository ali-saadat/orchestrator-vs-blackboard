"""Scenario S1 — interdependent project-plan reconciliation.

An over-ambitious plan must be reconciled into a self-consistent state under
interdependent constraints: cutting scope to fit the budget shortens the
timeline, which lowers the risk. Chosen because interdependence is exactly where
the shared-state harness earns its keep. (A linear routing task — where the
orchestrator wins — is a separate scenario; see docs/WHEN-TO-USE.md.)
"""
from __future__ import annotations

from ..core.state import PlanState

COST_PER_FEATURE_K = 15
BUDGET_CAP_K = 90
WEEKS_PER_FEATURE = 2
DEADLINE_WEEKS = 14

SCENARIO = (
    "Reconcile a project plan. The team asked for 8 features, but there is a "
    f"hard budget cap of ${BUDGET_CAP_K}k (each feature costs "
    f"${COST_PER_FEATURE_K}k), a {WEEKS_PER_FEATURE}-week build time per "
    f"feature, and a {DEADLINE_WEEKS}-week risk threshold. Scope, Budget, "
    "Timeline and Risk are interdependent."
)


def initial_state() -> PlanState:
    return PlanState(scope=8)


def risk_for(scope, timeline):
    if scope is None or timeline is None:
        return None
    if scope > 6 or timeline > DEADLINE_WEEKS:
        return "high"
    if scope > 4:
        return "medium"
    return "low"


def is_consistent(state: PlanState) -> bool:
    """The gate predicate: is the plan self-consistent under every constraint?"""
    s = state.scope
    return all(
        [
            state.budget_k is not None and state.budget_k <= BUDGET_CAP_K,
            state.max_scope is not None and s <= state.max_scope,
            state.timeline_weeks == s * WEEKS_PER_FEATURE,
            state.risk == risk_for(s, state.timeline_weeks),
        ]
    )
