"""BLACKBOARD harness — shared-state, event-driven.

Scheduling discipline (the classic control shell): all agents read/write ONE
shared state; a write re-triggers only the agents that SUBSCRIBE to the field
that changed. Work is proportional to the ripples, not to roster × rounds.

Bounded and auditable by construction:
  * the WORM log (every `state_write`) is the audit trail,
  * the GATE ends the run deterministically — the LLM never decides "done",
  * the control unit's `max_steps` guarantees the cascade can't run away.

Liveness (quiescence re-scan): pure subscription-driven re-triggering can strand
an agent — e.g. one negotiator reaches its target and goes silent while the
counterpart still needs to move, but nothing re-triggers the counterpart (the
classic blackboard "focus-of-attention exhausted" failure; Corkill/Lesser). When
the queue empties before the gate passes, we re-scan all agents once. A re-scan
that changes nothing is a genuine deadlock (reported as no-deal); otherwise its
writes re-seed the reactive loop. This makes the reachable fixpoint scheduler-
independent — required for the harness to be a fair, architecture-neutral
substrate — while staying event-driven whenever reactivity suffices.
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

        # seed: the kickoff — every agent hears the opening state once; after
        # this, only writes re-trigger (and only their subscribers)
        enqueue(self.registry.names(), "seed: kickoff")

        steps = 0
        while steps < self.config.max_steps:              # control unit cap
            # drain the reactive queue
            while queue and steps < self.config.max_steps:
                steps += 1
                name, why = queue.popleft()
                queued.discard(name)
                changes = await self.invoke(self.registry.get(name), trigger=why)
                for field in changes:                      # ripple to dependents
                    for n in subs.get(field, []):
                        self.rec.agent_retriggered(n, because=f"{field} changed")
                    enqueue(subs.get(field, []), f"{field} changed")
                if self.gate_passed():                     # deterministic gate
                    return self._finish(steps)
            # quiescence: queue empty, gate not passed — re-scan once for liveness
            if self.gate_passed() or steps >= self.config.max_steps:
                break
            made_change = False
            for name in self.registry.names():
                if steps >= self.config.max_steps:
                    break
                steps += 1
                changes = await self.invoke(self.registry.get(name),
                                            trigger="quiescence re-scan")
                if changes:
                    made_change = True
                    for field in changes:
                        for n in subs.get(field, []):
                            self.rec.agent_retriggered(n, because=f"{field} changed")
                        enqueue(subs.get(field, []), f"{field} changed")
                if self.gate_passed():
                    return self._finish(steps)
            if not made_change:                            # genuine deadlock
                break
        return self._finish(steps)
