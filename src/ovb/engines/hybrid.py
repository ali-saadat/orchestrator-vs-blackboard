"""HYBRID harness — a bounded blackboard inside an orchestrator.

Scheduling discipline: the supervisor keeps top-level control but delegates the
*tightly-coupled* sub-problem to a bounded blackboard, then finishes the
*independent* tail linearly.

For the job offer the live negotiation is Candidate ↔ Manager with HR as the
band referee (the band re-anchors both mid-talk), so those three share the board.
Finance only *reads* the settled deal to sign off the cap and the bonus — running
it once, after the core settles, avoids re-triggering it on every concession.

Honest note: the hybrid's edge here comes from *encoding the dependency structure*
(the architect knows which agents form the cycle). That knowledge is the price of
admission — hybrid wins when you can pre-identify the interdependent core. See
docs/HARNESS.md → when-to-use.
"""
from __future__ import annotations

from collections import deque

from ..contracts import EngineResult
from ..core.harness import Harness

CORE = {"Candidate", "Manager", "HR"}   # the live negotiation (incl. the band referee)
TAIL = ("Finance",)                     # signs off once, after the deal


class HybridHarness(Harness):
    control_model = "hybrid"

    async def run(self) -> EngineResult:
        self._start()
        steps = 0

        # Phase A — bounded blackboard over the coupled core {Guests, Budget}
        subs = self.registry.subscription_index(only=CORE)
        queue: deque[tuple[str, str]] = deque()
        queued: set[str] = set()

        def enqueue(names, why):
            for n in names:
                if n not in queued:
                    queue.append((n, why))
                    queued.add(n)

        core_names = [n for n in self.registry.names() if n in CORE]
        enqueue(core_names, "seed: kickoff (core)")
        # bounded blackboard over the core, with the same quiescence re-scan the
        # blackboard uses for liveness (a stranded core agent would otherwise
        # never re-trigger — see blackboard.py)
        # the core is settled once the salary is agreed (Candidate↔Manager, under
        # HR's band); then the tail signs. Breaking on that avoids a wasteful
        # detection re-scan when the core succeeds — the re-scan only runs to
        # rescue a genuinely stranded core (salary still open at quiescence).
        while steps < self.config.hybrid_cap:
            while queue and steps < self.config.hybrid_cap:
                steps += 1
                name, why = queue.popleft()
                queued.discard(name)
                changes = await self.invoke(self.registry.get(name), trigger=why)
                for field in changes:
                    for n in subs.get(field, []):
                        self.rec.agent_retriggered(n, because=f"{field} changed (core)")
                    enqueue(subs.get(field, []), f"{field} changed (core)")
            # drained naturally: if the salary is agreed the core has settled
            # (HR reacted to it via the normal ripple), so skip the re-scan; only
            # a still-open salary at quiescence means a stranded core to rescue
            if self.state.salary is not None or steps >= self.config.hybrid_cap:
                break
            made_change = False
            for name in core_names:
                if steps >= self.config.hybrid_cap:
                    break
                steps += 1
                changes = await self.invoke(self.registry.get(name),
                                            trigger="quiescence re-scan (core)")
                if changes:
                    made_change = True
                    for field in changes:
                        for n in subs.get(field, []):
                            self.rec.agent_retriggered(n, because=f"{field} changed (core)")
                        enqueue(subs.get(field, []), f"{field} changed (core)")
            if not made_change:
                break

        # Phase B — linear supervisor tail over the independent agents
        for name in TAIL:
            await self.invoke(self.registry.get(name), trigger="supervisor tail")

        return self._finish(steps)
