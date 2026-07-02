"""The four specialists as KnowledgeSources — IDENTICAL for all three harnesses.

Birthday-party planning. Rules close over `ScenarioParams`. Each `rule` is the
deterministic decision authority; the LLM narrates/validates.
  - Guests owns `guests`,  reacts to `max_guests`  (trim the list if the budget won't allow it)
  - Budget owns `cost`+`max_guests`, reacts to `guests`  (price it; cap the list)
  - Food   owns `pizzas`, reacts to `guests`
  - Vibe   owns `vibe`,   reacts to `guests`, `pizzas`
"""
from __future__ import annotations

from ..core.registry import AgentRegistry, KnowledgeSource
from . import task
from .task import ScenarioParams


def build_registry(params: "ScenarioParams | None" = None) -> AgentRegistry:
    p = params or ScenarioParams()

    def guests_rule(s):
        if s.max_guests is not None and s.guests > s.max_guests:
            return {"guests": s.max_guests}
        return {}

    def budget_rule(s):
        cost = s.guests * p.price_per_guest
        patch = {"cost": cost}
        if cost > p.budget_cap:
            patch["max_guests"] = p.budget_cap // p.price_per_guest
        else:
            patch["max_guests"] = s.guests
        return patch

    def food_rule(s):
        return {"pizzas": task.pizzas_for(s.guests, p)}

    def vibe_rule(s):
        return {"vibe": task.vibe_for(s.guests)}

    return AgentRegistry(
        sources=(
            KnowledgeSource(
                "Guests", ("guests",), ("max_guests",),
                "You own the guest list. Keep it within what the budget allows.",
                guests_rule,
            ),
            KnowledgeSource(
                "Budget", ("cost", "max_guests"), ("guests",),
                "You own the Budget. Price the party and cap the affordable guest count.",
                budget_rule,
            ),
            KnowledgeSource(
                "Food", ("pizzas",), ("guests",),
                "You own the Food. One pizza feeds three guests.",
                food_rule,
            ),
            KnowledgeSource(
                "Vibe", ("vibe",), ("guests", "pizzas"),
                "You own the Vibe. The party's feel follows the headcount.",
                vibe_rule,
            ),
        )
    )
