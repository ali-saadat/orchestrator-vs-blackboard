"""Scenario — negotiate a job offer until everyone says yes.

Four people close one deal:
  - Candidate = wants a high salary. Asks $130k, then comes down step by step.
  - Manager   = wants to hire, but cheap. Offers $100k, then goes up step by
                step — never above HR's band.
  - HR        = announces the hard salary band (max $110k base) mid-talk, and
                converts the candidate's concession into remote days
                (1 day per $5k they came down, 1–5).
  - Finance   = announces the total-pay cap ($124k) and signs off the signing
                bonus once the base is agreed (up to $8k, if there is room).

This is a real NEGOTIATION, not arithmetic: the two sides concede a fraction of
the gap each turn, HR's band lands mid-flight and re-anchors both, and the deal
emerges over many rounds — you cannot eyeball the final number.

Determinism (why the 3-way comparison stays fair): both sides converge toward
`target = min(midpoint(ask0, offer0), band_max)`. The manager's offer is clamped
at the target; when the offer reaches it, the candidate accepts ("that is their
final number"). So the DESTINATION is unique regardless of who speaks when —
only the number of turns differs, which is exactly what we measure.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core.state import PlanState

# defaults (used when no ScenarioParams is supplied) — all $ figures in $k
ASK0 = 130          # candidate's opening ask
OFFER0 = 100        # manager's opening offer
BAND_MAX = 110      # HR's hard cap on base salary
TOTAL_CAP = 124     # finance's cap on salary + bonus
BONUS_MAX = 8       # biggest possible signing bonus
STEP = 0.15         # each concession closes 15% of the current gap
K_PER_REMOTE_DAY = 5  # 1 remote day per $5k conceded


@dataclass(frozen=True)
class ScenarioParams:
    ask0: int = ASK0
    offer0: int = OFFER0
    band_max: int = BAND_MAX
    total_cap: int = TOTAL_CAP
    bonus_max: int = BONUS_MAX


def _p(params: "ScenarioParams | None") -> ScenarioParams:
    return params or ScenarioParams()


def scenario_text(params: "ScenarioParams | None" = None) -> str:
    p = _p(params)
    return (
        f"Close a job offer. The candidate asks ${p.ask0}k; the manager offers "
        f"${p.offer0}k. They concede step by step. HR's hard salary band tops out "
        f"at ${p.band_max}k, and Finance caps salary+bonus at ${p.total_cap}k "
        f"(bonus up to ${p.bonus_max}k). Remote days reward the candidate's "
        "concession (1 day per $5k, 1-5). Candidate, Manager, HR and Finance are "
        "interdependent — negotiate until every number agrees."
    )


# kept for imports/back-compat
SCENARIO = scenario_text()


def initial_state(params: "ScenarioParams | None" = None) -> PlanState:
    p = _p(params)
    return PlanState(ask=p.ask0, offer=p.offer0)


def target_salary(band_max, params: "ScenarioParams | None" = None) -> int:
    """Where the haggle lands: the midpoint of the opening positions, clamped by
    HR's band (once known)."""
    p = _p(params)
    mid = round((p.ask0 + p.offer0) / 2)
    return mid if band_max is None else min(mid, band_max)


def concede(current: int, toward: int, other: int) -> int:
    """One negotiation step: close STEP of the current gap (at least $1k),
    never crossing `toward` (the target)."""
    gap = abs(current - other)
    move = max(1, round(gap * STEP))
    if current > toward:                 # candidate coming down
        return max(toward, current - move)
    if current < toward:                 # manager going up
        return min(toward, current + move)
    return current


def remote_for(salary, params: "ScenarioParams | None" = None):
    """1 remote day per $5k the candidate conceded from the opening ask (1-5)."""
    p = _p(params)
    if salary is None:
        return None
    return max(1, min(5, (p.ask0 - salary) // K_PER_REMOTE_DAY))


def bonus_for(salary, total_cap, params: "ScenarioParams | None" = None):
    """Signing bonus: up to bonus_max, if the total-pay cap leaves room."""
    p = _p(params)
    if salary is None or total_cap is None:
        return None
    return max(0, min(p.bonus_max, total_cap - salary))


def is_consistent(state: PlanState, params: "ScenarioParams | None" = None) -> bool:
    """The gate: is the deal fully agreed and inside every rule?"""
    p = _p(params)
    return all(
        [
            state.salary is not None,
            state.ask == state.offer == state.salary,
            state.band_max is not None and state.salary is not None
            and state.salary <= state.band_max,
            state.total_cap is not None and state.bonus is not None
            and state.salary is not None
            and state.salary + state.bonus <= state.total_cap,
            state.bonus == bonus_for(state.salary, state.total_cap, p),
            state.remote == remote_for(state.salary, p),
        ]
    )
