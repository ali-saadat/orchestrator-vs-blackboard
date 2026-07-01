"""The three harness topologies. Each subclasses core.Harness and implements
ONLY `run()` — the scheduling discipline. Everything else (the harness step, the
gate, token/cost/write recording) is shared, which is what makes them a fair
comparison."""
from .blackboard import BlackboardHarness
from .hybrid import HybridHarness
from .orchestrator import OrchestratorHarness

ENGINES = {
    "orchestrator": OrchestratorHarness,
    "blackboard": BlackboardHarness,
    "hybrid": HybridHarness,
}

__all__ = ["OrchestratorHarness", "BlackboardHarness", "HybridHarness", "ENGINES"]
