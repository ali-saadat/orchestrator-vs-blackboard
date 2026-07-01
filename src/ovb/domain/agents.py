"""The four specialists as KnowledgeSources — identical for all three harnesses.

Each `rule` is the deterministic decision authority; the LLM narrates/validates.
`owns`/`subscribes` are the wiring the blackboard and hybrid schedule on and the
orchestrator ignores.
"""
from __future__ import annotations

from ..core.registry import AgentRegistry, KnowledgeSource
from . import task


def _scope_rule(s):
    if s.max_scope is not None and s.scope > s.max_scope:
        return {"scope": s.max_scope}
    return {}


def _budget_rule(s):
    cost = s.scope * task.COST_PER_FEATURE_K
    patch = {"budget_k": cost}
    if cost > task.BUDGET_CAP_K:
        patch["max_scope"] = task.BUDGET_CAP_K // task.COST_PER_FEATURE_K
    else:
        patch["max_scope"] = s.scope
    return patch


def _timeline_rule(s):
    return {"timeline_weeks": s.scope * task.WEEKS_PER_FEATURE}


def _risk_rule(s):
    return {"risk": task.risk_for(s.scope, s.timeline_weeks)}


def build_registry() -> AgentRegistry:
    return AgentRegistry(
        sources=(
            KnowledgeSource(
                "Scope", ("scope",), ("max_scope",),
                "You are the Scope owner. Keep feature count within the budget ceiling.",
                _scope_rule,
            ),
            KnowledgeSource(
                "Budget", ("budget_k", "max_scope"), ("scope",),
                "You are the Budget owner. Compute cost and enforce the hard cap.",
                _budget_rule,
            ),
            KnowledgeSource(
                "Timeline", ("timeline_weeks",), ("scope",),
                "You are the Timeline owner. Delivery time follows the scope.",
                _timeline_rule,
            ),
            KnowledgeSource(
                "Risk", ("risk",), ("scope", "timeline_weeks"),
                "You are the Risk owner. Grade risk from scope and timeline.",
                _risk_rule,
            ),
        )
    )
