"""BLACKBOARD harness — shared-state, event-driven.

Scheduling discipline (the classic control shell): all agents read/write ONE
shared state; a write re-triggers only the agents that SUBSCRIBE to the field
that changed. Work is proportional to the ripples, not to roster × rounds.

Bounded and auditable by construction:
  * the WORM log (every `state_write`) is the audit trail,
  * the GATE ends the run deterministically — the LLM never decides "done",
  * the control unit's `max_steps` guarantees the cascade can't run away.
"""
from __future__ import annotations

from collections import deque

from ..contracts import EngineResult
from ..core.harness import Harness


class BlackboardHarness(Harness):
    control_model = "blackboard"

    async def run(self) -> EngineResult:
        self._start()
        subs = self.registry.subscription_index()
        queue: deque[tuple[str, str]] = deque()
        queued: set[str] = set()

        def enqueue(names, why):
            for n in names:
                if n not in queued:
                    queue.append((n, why))
                    queued.add(n)

        # seed: the requirement lands on the board as `scope`, waking its subscribers
        enqueue(subs.get("scope", []), "seed: scope posted")

        steps = 0
        while queue and steps < self.config.max_steps:   # control unit cap
            steps += 1
            name, why = queue.popleft()
            queued.discard(name)
            changes = await self.invoke(self.registry.get(name), trigger=why)
            for field in changes:                          # ripple to dependents
                for n in subs.get(field, []):
                    self.rec.agent_retriggered(n, because=f"{field} changed")
                enqueue(subs.get(field, []), f"{field} changed")
            if self.gate_passed():                         # deterministic gate
                break
        return self._finish(steps)
