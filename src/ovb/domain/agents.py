"""The four negotiators as KnowledgeSources — IDENTICAL for all three harnesses.

Job-offer negotiation. Rules close over `ScenarioParams`. Each `rule` is the
deterministic decision authority (a concession strategy); the LLM narrates.
  - Candidate owns `ask`;             reacts to `offer`, `band_max`
  - Manager   owns `offer`+`salary`;  reacts to `ask`, `band_max`
  - HR        owns `band_max`+`remote`; reacts to `ask`, `salary`
  - Finance   owns `total_cap`+`bonus`; reacts to `ask`, `salary`

Concession protocol (deterministic, order-independent destination): both sides
step toward `target = min(midpoint of openings, band)`; the offer is clamped at
the target; when the offer reaches it, the candidate accepts the final number.
"""
from __future__ import annotations

from ..core.registry import AgentRegistry, KnowledgeSource
from . import task
from .task import ScenarioParams


def build_registry(params: "ScenarioParams | None" = None) -> AgentRegistry:
    p = params or ScenarioParams()

    def candidate_rule(s):
        if s.salary is not None or s.ask == s.offer:
            return {}
        tgt = task.target_salary(s.band_max, p)
        if s.offer >= tgt:                       # their final number — accept it
            return {"ask": s.offer}
        new_ask = task.concede(s.ask, tgt, s.offer)
        return {"ask": new_ask} if new_ask != s.ask else {}

    def manager_rule(s):
        if s.salary is not None:
            return {}
        if s.ask == s.offer:                     # hands shaken — write the deal
            return {"salary": s.ask}
        tgt = task.target_salary(s.band_max, p)
        new_offer = task.concede(s.offer, tgt, s.ask)
        patch = {}
        if new_offer != s.offer:
            patch["offer"] = new_offer
        if new_offer == s.ask:                   # we just met — close it now
            patch["salary"] = new_offer
        return patch

    def hr_rule(s):
        patch = {}
        if s.band_max is None:
            patch["band_max"] = p.band_max       # announce the hard band
        if s.salary is not None and s.remote is None:
            patch["remote"] = task.remote_for(s.salary, p)
        return patch

    def finance_rule(s):
        patch = {}
        if s.total_cap is None:
            patch["total_cap"] = p.total_cap     # announce the total-pay cap
        if s.salary is not None and s.bonus is None:
            cap = s.total_cap if s.total_cap is not None else p.total_cap
            patch["bonus"] = task.bonus_for(s.salary, cap, p)
        return patch

    return AgentRegistry(
        sources=(
            KnowledgeSource(
                "Candidate", ("ask",), ("offer", "band_max"),
                "You are the Candidate. Negotiate the salary you deserve, "
                "conceding step by step; accept the band cap when it is final.",
                candidate_rule,
            ),
            KnowledgeSource(
                "Manager", ("offer", "salary"), ("ask", "band_max"),
                "You are the hiring Manager. Raise your offer step by step, "
                "never above HR's band; close the deal when you meet.",
                manager_rule,
            ),
            KnowledgeSource(
                "HR", ("band_max", "remote"), ("salary",),
                "You are HR. Announce the hard salary band, and grant remote "
                "days for the candidate's concession (1 day per $5k, 1-5).",
                hr_rule,
            ),
            KnowledgeSource(
                "Finance", ("total_cap", "bonus"), ("salary",),
                "You are Finance. Announce the total-pay cap and approve the "
                "signing bonus once the base is agreed (up to $8k, if room).",
                finance_rule,
            ),
        )
    )
