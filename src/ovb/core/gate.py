"""The gate — a deterministic termination check.

Design rule the whole repo insists on: **the LLM never renders the final
verdict.** A run ends when a deterministic gate says the state is consistent (or
the control unit's cap trips). The SAME gate instance is shared by every harness
— an orchestrator that stopped on this gate and a blackboard that stopped on it
are being judged by identical code, which is what keeps the comparison fair.
"""
from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable


@runtime_checkable
class Gate(Protocol):
    spec: str
    def passed(self, state) -> bool: ...


class PredicateGate:
    """Wraps a pure predicate `(state) -> bool`. `spec` is a stable label used in
    the fairness fingerprint."""

    def __init__(self, predicate: Callable[[object], bool], spec: str):
        self._predicate = predicate
        self.spec = spec

    def passed(self, state) -> bool:
        return bool(self._predicate(state))
