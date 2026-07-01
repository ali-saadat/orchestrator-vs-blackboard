"""The specialist agents — IDENTICAL for both control models.

Each agent:
  - *owns* one or more fields on the shared state,
  - is *triggered* by changes to certain fields (its subscriptions),
  - exposes ``act(view, llm) -> (patch, rationale, usage)``.

The decision rules live here so mock mode is deterministic. In real mode the
same rule is *narrated* by the LLM (so token/latency numbers are real), but the
numeric decision is still validated against the rule — the model can't send the
plan off the rails, which keeps the two topologies comparable.

Note there is nothing here about *how* agents are scheduled. Scheduling is the
only thing the two engines differ on; the agents don't know or care which engine
is driving them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import task


@dataclass
class Agent:
    name: str
    owns: list          # fields this agent may write
    subscribes: list    # field changes that (re)trigger this agent
    role: str           # system prompt persona (used verbatim in real mode)
    rule: Callable      # (state) -> dict patch

    def act(self, view: dict, llm) -> tuple:
        patch = self.rule(view)
        # keep only genuine changes
        patch = {k: v for k, v in patch.items() if view.get(k) != v}
        rationale = self._narrate(patch)
        comp = llm.complete(system=self.role, prompt=_prompt(self, view),
                            expect=rationale)
        # In real mode `comp.text` is the model's own narration; the numeric
        # patch is still the validated rule output.
        return patch, comp.text, comp.usage

    def _narrate(self, patch: dict) -> str:
        if not patch:
            return f"{self.name}: already consistent with my constraint; no change."
        parts = ", ".join(f"{k}->{v}" for k, v in patch.items())
        return f"{self.name}: adjusting {parts}."


def _prompt(agent: "Agent", view: dict) -> str:
    return (
        f"Current plan state: {view}. You own {agent.owns}. "
        "Apply your constraint and report the single change you make (if any)."
    )


# ---- the four specialists -------------------------------------------------

def _scope_rule(s):
    if s["max_scope"] is not None and s["scope"] > s["max_scope"]:
        return {"scope": s["max_scope"]}
    return {}


def _budget_rule(s):
    cost = s["scope"] * task.COST_PER_FEATURE_K
    patch = {"budget_k": cost}
    if cost > task.BUDGET_CAP_K:
        patch["max_scope"] = task.BUDGET_CAP_K // task.COST_PER_FEATURE_K
    else:
        patch["max_scope"] = s["scope"]
    return patch


def _timeline_rule(s):
    return {"timeline_weeks": s["scope"] * task.WEEKS_PER_FEATURE}


def _risk_rule(s):
    return {"risk": task.risk_for(s["scope"], s["timeline_weeks"])}


def build_agents() -> list:
    """Fresh agent instances (no shared mutable state between runs)."""
    return [
        Agent(
            "Scope", ["scope"], ["max_scope"],
            "You are the Scope owner. Keep feature count within the budget ceiling.",
            _scope_rule,
        ),
        Agent(
            "Budget", ["budget_k", "max_scope"], ["scope"],
            "You are the Budget owner. Compute cost and enforce the hard cap.",
            _budget_rule,
        ),
        Agent(
            "Timeline", ["timeline_weeks"], ["scope"],
            "You are the Timeline owner. Delivery time follows the scope.",
            _timeline_rule,
        ),
        Agent(
            "Risk", ["risk"], ["scope", "timeline_weeks"],
            "You are the Risk owner. Grade risk from scope and timeline.",
            _risk_rule,
        ),
    ]
