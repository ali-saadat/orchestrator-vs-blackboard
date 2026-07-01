"""ORCHESTRATOR harness — hub-and-spoke, supervisor-routed.

Scheduling discipline: a central supervisor invokes each agent in a FIXED order.
Agents are isolated (each `invoke` gets a fresh view; they never see each other).
With no shared state and no mid-task reaction, the only way to resolve an
interdependency is to sweep the whole roster again — and to confirm convergence
you pay one final no-op sweep. That confirming sweep is the hub tax.

`orch_early_exit` optionally gives the orchestrator the SAME deterministic gate
the blackboard uses, so you can report both variants and never be accused of
handicapping it (see docs/HARNESS.md → fairness).
"""
from __future__ import annotations

from ..contracts import EngineResult
from ..core.harness import Harness

ORDER = ("Scope", "Budget", "Timeline", "Risk")


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
