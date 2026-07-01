"""The four specialists as KnowledgeSources — identical for all three harnesses.

Rules close over `ScenarioParams`, so the same registry logic reconciles whatever
budget/scope "prompt" the UI supplies. Each `rule` is the deterministic decision
authority; the LLM narrates/validates.
"""
from __future__ import annotations

from ..core.registry import AgentRegistry, KnowledgeSource
from . import task
from .task import ScenarioParams


def build_registry(params: "ScenarioParams | None" = None) -> AgentRegistry:
    p = params or ScenarioParams()

    def scope_rule(s):
        if s.max_scope is not None and s.scope > s.max_scope:
            return {"scope": s.max_scope}
        return {}

    def budget_rule(s):
        cost = s.scope * p.cost_per_feature_k
        patch = {"budget_k": cost}
        if cost > p.budget_cap_k:
            patch["max_scope"] = p.budget_cap_k // p.cost_per_feature_k
        else:
            patch["max_scope"] = s.scope
        return patch

    def timeline_rule(s):
        return {"timeline_weeks": s.scope * p.weeks_per_feature}

    def risk_rule(s):
        return {"risk": task.risk_for(s.scope, s.timeline_weeks, p)}

    return AgentRegistry(
        sources=(
            KnowledgeSource(
                "Scope", ("scope",), ("max_scope",),
                "You are the Scope owner. Keep feature count within the budget ceiling.",
                scope_rule,
            ),
            KnowledgeSource(
                "Budget", ("budget_k", "max_scope"), ("scope",),
                "You are the Budget owner. Compute cost and enforce the hard cap.",
                budget_rule,
            ),
            KnowledgeSource(
                "Timeline", ("timeline_weeks",), ("scope",),
                "You are the Timeline owner. Delivery time follows the scope.",
                timeline_rule,
            ),
            KnowledgeSource(
                "Risk", ("risk",), ("scope", "timeline_weeks"),
                "You are the Risk owner. Grade risk from scope and timeline.",
                risk_rule,
            ),
        )
    )
