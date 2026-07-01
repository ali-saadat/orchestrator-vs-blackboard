"""The shared problem both topologies must solve.

Scenario: an over-ambitious project plan must be reconciled into a
self-consistent state under *interdependent* constraints. Changing one field
forces others to change — which is exactly the situation that separates a
reactive blackboard from a fixed-order orchestrator.

We deliberately pick an interdependent task. On a purely linear task (classify
-> route -> answer) the orchestrator is the better fit and would win; see
docs/WHEN-TO-USE.md. This scenario is chosen to expose the blackboard's edge:
one write should ripple to just the agents it affects.
"""
from __future__ import annotations

COST_PER_FEATURE_K = 15     # $k to build one feature
BUDGET_CAP_K = 90           # hard budget ceiling ($k)
WEEKS_PER_FEATURE = 2       # delivery time per feature
DEADLINE_WEEKS = 14         # anything longer is 'high' risk

SCENARIO = (
    "Reconcile a project plan. The team asked for 8 features, but there is a "
    f"hard budget cap of ${BUDGET_CAP_K}k (each feature costs "
    f"${COST_PER_FEATURE_K}k), a {WEEKS_PER_FEATURE}-week build time per "
    f"feature, and a {DEADLINE_WEEKS}-week risk threshold. Scope, Budget, "
    "Timeline and Risk are interdependent: cutting scope to fit the budget "
    "shortens the timeline, which lowers the risk. Find the consistent plan."
)


def initial_state() -> dict:
    return {
        "scope": 8,              # requested features   (owned by ScopeAgent)
        "max_scope": None,       # budget ceiling        (owned by BudgetAgent)
        "budget_k": None,        # computed cost         (owned by BudgetAgent)
        "timeline_weeks": None,  # delivery time         (owned by TimelineAgent)
        "risk": None,            # low|medium|high       (owned by RiskAgent)
    }


def risk_for(scope, timeline):
    if scope is None or timeline is None:
        return None
    if scope > 6 or timeline > DEADLINE_WEEKS:
        return "high"
    if scope > 4:
        return "medium"
    return "low"


def is_consistent(state: dict) -> bool:
    """The gate: is the plan self-consistent under every constraint?"""
    s = state["scope"]
    return all(
        [
            state["budget_k"] is not None and state["budget_k"] <= BUDGET_CAP_K,
            state["max_scope"] is not None and s <= state["max_scope"],
            state["timeline_weeks"] == s * WEEKS_PER_FEATURE,
            state["risk"] == risk_for(s, state["timeline_weeks"]),
        ]
    )
