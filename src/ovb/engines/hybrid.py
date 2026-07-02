"""HYBRID harness — a bounded blackboard inside an orchestrator.

Scheduling discipline: the supervisor keeps top-level control but delegates the
*tightly-coupled* sub-problem to a bounded blackboard, then finishes the
*independent* tail linearly.

For the party plan the tight cycle is Guests ↔ Budget (a budget cap trims the
guest list, which changes the cost, …). Food and Chairs only *read* the settled
headcount, so they need no re-triggering — running them once, after the core
settles, avoids the pure blackboard's "Chairs sets out 15, then re-sets to 12"
churn.

Honest note: the hybrid's edge here comes from *encoding the dependency structure*
(the architect knows which agents form the cycle). That knowledge is the price of
admission — hybrid wins when you can pre-identify the interdependent core. See
docs/HARNESS.md → when-to-use.
"""
from __future__ import annotations

from collections import deque

from ..contracts import EngineResult
from ..core.harness import Harness

CORE = {"Guests", "Budget"}      # the tightly-coupled cycle (want-vs-afford)
TAIL = ("Food", "Chairs")        # independent, downstream-only


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

        enqueue(subs.get("guests", []), "seed: guest list posted (core)")
        while queue and steps < self.config.hybrid_cap:
            steps += 1
            name, why = queue.popleft()
            queued.discard(name)
            changes = await self.invoke(self.registry.get(name), trigger=why)
            for field in changes:
                for n in subs.get(field, []):
                    self.rec.agent_retriggered(n, because=f"{field} changed (core)")
                enqueue(subs.get(field, []), f"{field} changed (core)")

        # Phase B — linear supervisor tail over the independent agents
        for name in TAIL:
            await self.invoke(self.registry.get(name), trigger="supervisor tail")

        return self._finish(steps)
