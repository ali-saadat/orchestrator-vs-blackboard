"""Scenario — plan a birthday party that fits a budget.

Four friends agree on one party plan:
  - Guests = the guest list. You'd love to invite 15 people.
  - Budget = the money; a hard cap. Cost = guests × $50/head (all-in: food,
             drinks, cake), so a long list may not fit — Budget then caps
             how many you can afford.
  - Food   = the pizza order; one pizza feeds 3 guests.
  - Chairs = the chairs to set out; every guest needs exactly one chair.

Interdependence (why the shared board helps): the guest list drives everything.
Trimming it to fit the budget also changes the pizza order and the chair count,
so a change ripples — but only to the friends who depend on the headcount. The
tightly coupled pair is Guests ↔ Budget (want-vs-afford); Food and Chairs just
follow the final number.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core.state import PlanState

# defaults (used when no ScenarioParams is supplied)
PRICE_PER_GUEST = 50     # $ per guest (food, drinks, favors)
BUDGET_CAP = 600         # $ hard cap
GUESTS_PER_PIZZA = 3     # one pizza feeds 3
WANTED_GUESTS = 15       # the wish-list headcount


@dataclass(frozen=True)
class ScenarioParams:
    wanted_guests: int = WANTED_GUESTS   # how many you'd love to invite (the "ask")
    budget_cap: int = BUDGET_CAP         # the hard $ cap
    price_per_guest: int = PRICE_PER_GUEST
    guests_per_pizza: int = GUESTS_PER_PIZZA


def _p(params: "ScenarioParams | None") -> ScenarioParams:
    return params or ScenarioParams()


def scenario_text(params: "ScenarioParams | None" = None) -> str:
    p = _p(params)
    return (
        f"Plan a birthday party. You want to invite {p.wanted_guests} guests, but "
        f"there is a hard budget cap of ${p.budget_cap} (each guest costs "
        f"${p.price_per_guest} all-in); one pizza feeds {p.guests_per_pizza} guests, "
        "and every guest needs one chair. Guests, Budget, Food and Chairs are "
        "interdependent — find the best party that fits the budget."
    )


# kept for imports/back-compat
SCENARIO = scenario_text()


def initial_state(params: "ScenarioParams | None" = None) -> PlanState:
    return PlanState(guests=_p(params).wanted_guests)


def chairs_for(guests):
    """Every guest needs exactly one chair."""
    return None if guests is None else guests


def pizzas_for(guests, params: "ScenarioParams | None" = None):
    """One pizza feeds `guests_per_pizza` people (round up so nobody goes hungry)."""
    p = _p(params)
    return None if guests is None else -(-guests // p.guests_per_pizza)


def is_consistent(state: PlanState, params: "ScenarioParams | None" = None) -> bool:
    """The gate: is this a valid, self-consistent party plan?"""
    p = _p(params)
    g = state.guests
    return all(
        [
            state.cost is not None and state.cost <= p.budget_cap,
            state.max_guests is not None and g <= state.max_guests,
            state.pizzas == pizzas_for(g, p),
            state.chairs == chairs_for(g),
        ]
    )
