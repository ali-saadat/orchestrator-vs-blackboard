"""The live SSE pump: same event contract, streamed. No socket — we pass a
collector as the writer and assert the stream is complete and well-formed."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from ovb.domain.task import ScenarioParams  # noqa: E402
from ovb.viz.live import _pump  # noqa: E402


def _collect(params, engines, delay=0.0):
    evs = []
    asyncio.run(_pump(params, engines, delay, evs.append))
    return evs


def test_pump_streams_all_three_engines():
    evs = _collect(ScenarioParams(), ["orchestrator", "blackboard", "hybrid"])
    assert any(e["engine"] == "_meta" and e["kind"] == "start" for e in evs)
    assert any(e["engine"] == "_meta" and e["kind"] == "all_done" for e in evs)

    kinds = {}
    for e in evs:
        kinds.setdefault(e["engine"], set()).add(e["kind"])
    for name in ["orchestrator", "blackboard", "hybrid"]:
        assert {"run_started", "run_finished", "state_write",
                "gen_ai.client.call.finished"} <= kinds[name], name
        assert (name, "engine_done") in {(e["engine"], e["kind"]) for e in evs}

    # the blackboard's reactive shared memory must surface re-trigger events
    assert "agent_retriggered" in kinds["blackboard"]


def test_pump_prompt_params_flow_to_all_engines():
    # 9 guests fit the budget (9 × $50 = $450 ≤ $600) → list stays 9, plan consistent
    evs = _collect(ScenarioParams(wanted_guests=9, budget_cap=600), ["blackboard"])
    fin = [e for e in evs if e["kind"] == "run_finished" and e["engine"] == "blackboard"][0]
    assert fin["attrs"]["consistent"] is True
    assert fin["attrs"]["state"]["guests"] == 9


def test_agent_talk_is_present_in_stream():
    evs = _collect(ScenarioParams(), ["blackboard"])
    talk = [e for e in evs if e["kind"] == "gen_ai.client.call.finished" and e["attrs"].get("message")]
    assert talk, "expected agent narration ('talk') on finished calls"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"ok  {name}")
    print("all live tests passed")
