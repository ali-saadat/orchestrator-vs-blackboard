"""Typed plan state + the reducer.

Every state transition goes through `apply_patch`, never attribute assignment,
so each mutation is (a) ownership-checked, (b) diffed, (c) emitted as a discrete
change the harness turns into a WORM `state_write` event. Producing writes from
ONE engine-agnostic function is what makes the two topologies' audit logs
comparable.

`apply_patch` is also the code-level answer to the prompt-injection blast-radius
concern: an agent — even a subverted one — cannot write outside its `owns` set;
the reducer raises `OwnershipError`. (See docs/HARNESS.md → security.)
"""
from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel, ConfigDict


class PlanState(BaseModel):
    """The typed deal state for the job-offer negotiation scenario.

    In the blackboard and hybrid core this is the SHARED board all agents read and
    write (and re-trigger on); in the orchestrator it is the supervisor's
    accumulated state, updated only by fixed-order sweeps (no shared board, no
    re-triggering). Domain-specific by design — a new scenario ships a new state
    model. The kernel only relies on it being a frozen pydantic model with a
    `fingerprint`.
    """

    model_config = ConfigDict(frozen=True)
    ask: int                          # candidate's current salary ask, $k (owned by Candidate)
    offer: int                        # manager's current salary offer, $k (owned by Manager)
    band_max: int | None = None       # HR's hard cap on base salary, $k (owned by HR)
    total_cap: int | None = None      # finance's cap on salary+bonus, $k (owned by Finance)
    salary: int | None = None         # the agreed base, $k (owned by Manager, when ask==offer)
    bonus: int | None = None          # signing bonus, $k (owned by Finance)
    remote: int | None = None         # remote days per week (owned by HR)

    def fingerprint(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()[:16]


class OwnershipError(RuntimeError):
    def __init__(self, owner: str, fields: set[str]):
        super().__init__(f"{owner} may not write fields {sorted(fields)}")
        self.owner = owner
        self.fields = fields


def apply_patch(
    state: PlanState, patch: dict[str, Any], *, owner: str, owns: tuple[str, ...]
) -> tuple[PlanState, dict[str, tuple[Any, Any]]]:
    """Return (new_state, changes) where changes maps field -> (old, new) for
    fields that GENUINELY changed. Raises OwnershipError on out-of-scope writes."""
    bad = set(patch) - set(owns)
    if bad:
        raise OwnershipError(owner, bad)
    changes: dict[str, tuple[Any, Any]] = {}
    updates: dict[str, Any] = {}
    for field, value in patch.items():
        old = getattr(state, field)
        if old != value:
            changes[field] = (old, value)
            updates[field] = value
    new_state = state.model_copy(update=updates) if updates else state
    return new_state, changes
