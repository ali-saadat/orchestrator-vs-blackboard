"""Deterministic smoke tests (mock mode, no network). Sync functions that drive
the async engines via asyncio.run, so no pytest-asyncio dependency is required."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from ovb.config import RunConfig  # noqa: E402
from ovb.core.gate import PredicateGate  # noqa: E402
from ovb.core.state import OwnershipError, PlanState, apply_patch  # noqa: E402
from ovb.domain import agents, task  # noqa: E402
from ovb.eval.compare import FairnessContract  # noqa: E402
from ovb.eval.runner import run_all  # noqa: E402

EXPECTED = {"ask": 110, "offer": 110, "band_max": 110, "total_cap": 124,
            "salary": 110, "bonus": 8, "remote": 4}


def _run():
    return asyncio.run(run_all(RunConfig()))


def test_all_three_converge_to_same_state():
    results = _run()
    for name, r in results.items():
        assert r.consistent, name
        assert r.state == EXPECTED, name


def test_headline_call_counts():
    r = _run()
    assert r["orchestrator"].recorder.n_calls == 24
    assert r["blackboard"].recorder.n_calls == 14
    assert r["hybrid"].recorder.n_calls == 13
    assert r["blackboard"].recorder.n_calls < r["orchestrator"].recorder.n_calls


def test_orchestrator_pays_the_hub_tax():
    r = _run()
    assert r["orchestrator"].recorder.n_wasted > 0     # confirming no-op sweep
    assert r["blackboard"].recorder.n_wasted == 0


def test_blackboard_cheaper_tokens_and_cost():
    r = _run()
    o, b = r["orchestrator"].recorder, r["blackboard"].recorder
    assert b.total_usage.total < o.total_usage.total
    assert b.total_cost_usd < o.total_cost_usd


def test_fairness_contract_holds():
    r = _run()
    FairnessContract.assert_comparable(
        r, registry=agents.build_registry(),
        gate=PredicateGate(task.is_consistent, spec="reconcile.is_consistent/v1"),
        config=RunConfig(),
    )


def test_ownership_reducer_blocks_out_of_scope_writes():
    st = PlanState(ask=130, offer=100)
    try:
        apply_patch(st, {"salary": 110}, owner="HR", owns=("band_max", "remote"))
        assert False, "expected OwnershipError"
    except OwnershipError:
        pass


def test_gate_predicate():
    assert task.is_consistent(PlanState(**EXPECTED))
    assert not task.is_consistent(PlanState(**{**EXPECTED, "ask": 130}))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all smoke tests passed")
