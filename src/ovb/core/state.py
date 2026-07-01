"""Shared typed state + the reducer.

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
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class PlanState(BaseModel):
    """The shared blackboard/plan for the reconciliation scenario.

    Domain-specific by design — a new scenario ships a new state model. The
    kernel only relies on it being a frozen pydantic model with a `fingerprint`.
    """

    model_config = ConfigDict(frozen=True)
    scope: int
    max_scope: int | None = None
    budget_k: int | None = None
    timeline_weeks: int | None = None
    risk: Literal["low", "medium", "high"] | None = None

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
