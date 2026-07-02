"""ORCHESTRATOR harness — hub-and-spoke, supervisor-routed.

Scheduling discipline: a central supervisor invokes each agent in a FIXED order
over its accumulated plan state. There is no shared *board* the agents write to
directly and no reactive re-triggering — an agent never wakes because another
agent wrote a field; coordination happens only when the supervisor re-invokes on
the next sweep. Each `invoke` is a fresh model call (the agent sees the
supervisor's current state, not the other agents' context or reasoning). To
resolve an interdependency the supervisor must sweep the whole roster again, and
to confirm convergence it pays one final no-op sweep — the hub tax.

`orch_early_exit` optionally gives the orchestrator the SAME deterministic gate
the blackboard uses, so you can report both variants and never be accused of
handicapping it (see docs/HARNESS.md → fairness).
"""
from __future__ import annotations

from ..contracts import EngineResult
from ..core.harness import Harness

ORDER = ("Guests", "Budget", "Food", "Vibe")


class OrchestratorHarness(Harness):
    control_model = "orchestrator"

    async def run(self) -> EngineResult:
        self._start()
        rounds = 0
        for r in range(1, self.config.max_rounds + 1):
            rounds = r
            changed_any = False
            for name in ORDER:
                changes = await self.invoke(self.registry.get(name),
                                            trigger=f"sweep {r}")
                if changes:
                    changed_any = True
                if self.config.orch_early_exit and self.gate_passed():
                    return self._finish(rounds)
            if not changed_any:
                break
        return self._finish(rounds)
