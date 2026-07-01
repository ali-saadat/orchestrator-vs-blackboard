"""Smoke tests: both engines must reach the SAME consistent plan, and the
blackboard must do it in fewer calls than the orchestrator on this
interdependent task. Pure mock mode — deterministic, no network."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ovb import blackboard, orchestrator, task  # noqa: E402
from ovb.llm import MockLLM  # noqa: E402

EXPECTED = {
    "scope": 6,
    "max_scope": 6,
    "budget_k": 90,
    "timeline_weeks": 12,
    "risk": "medium",
}


def test_both_converge_to_same_state():
    orch = orchestrator.run(MockLLM())
    bb = blackboard.run(MockLLM())
    assert orch["consistent"] and bb["consistent"]
    assert orch["state"] == EXPECTED
    assert bb["state"] == EXPECTED
    assert orch["state"] == bb["state"]


def test_blackboard_is_cheaper_on_interdependent_task():
    orch = orchestrator.run(MockLLM())
    bb = blackboard.run(MockLLM())
    assert bb["recorder"].n_calls < orch["recorder"].n_calls
    assert bb["recorder"].total_usage.total < orch["recorder"].total_usage.total


def test_orchestrator_has_wasted_calls():
    # the confirming final sweep changes nothing — that's the hub tax
    orch = orchestrator.run(MockLLM())
    assert orch["recorder"].n_wasted > 0


def test_gate_holds():
    assert task.is_consistent(EXPECTED)
    bad = dict(EXPECTED, scope=8)
    assert not task.is_consistent(bad)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all smoke tests passed")
