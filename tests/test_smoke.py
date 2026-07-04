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


def test_free_patch_parsing():
    from ovb.core.registry import parse_free_patch
    owns = ("ask",)
    assert parse_free_patch('I will meet you halfway.\n{"ask": 120}', owns) == {"ask": 120}
    assert parse_free_patch('{"ask": 125} no wait {"ask": 118.6}', owns) == {"ask": 119}
    assert parse_free_patch('{"ask": 120, "offer": 105}', owns) == {"ask": 120}  # foreign field dropped
    assert parse_free_patch("I hold my position. {}", owns) == {}
    assert parse_free_patch("no json at all", owns) == {}
    assert parse_free_patch('{"ask": "a lot"}', owns) == {}
    assert parse_free_patch("", owns) == {}


def test_free_mode_model_decides():
    """In free mode the LLM's JSON tail IS the decision; ownership still holds."""
    from ovb.contracts import Completion, Usage

    class ScriptedLLM:
        def __init__(self, text):
            self.text = text
            self.prompts = []

        async def complete(self, *, system, prompt, expect="", tools=(),
                           tools_exec=None):
            self.prompts.append(prompt)
            assert "Decide your next move" in prompt      # decision prompt, not narration
            return Completion(text=self.text, usage=Usage(input_tokens=10, output_tokens=5))

    cand = agents.build_registry().get("Candidate")
    state = PlanState(ask=130, offer=100)
    res = asyncio.run(cand.act(state, ScriptedLLM('Meet me closer. {"ask": 121}'),
                               None, free=True))
    assert res.patch == {"ask": 121}
    # the persuasion channel: recent words reach the next agent's prompt
    llm = ScriptedLLM('Fine — done. {"ask": 115}')
    asyncio.run(cand.act(state, llm, None, free=True,
                         talk=("Manager: 115 is my final number.",)))
    assert "Recent talk:" in llm.prompts[0]
    assert "Manager: 115 is my final number." in llm.prompts[0]
    # a move on a field the agent does not own is dropped at parse time...
    res2 = asyncio.run(cand.act(state, ScriptedLLM('{"salary": 999}'), None, free=True))
    assert res2.patch == {}
    # ...and the reducer would block it anyway (defense in depth)


def test_free_gate_is_agreed():
    ok = PlanState(ask=112, offer=112, band_max=115, total_cap=124,
                   salary=112, bonus=5, remote=2)
    assert task.is_agreed(ok)                         # any closed in-limits deal passes
    assert not task.is_consistent(ok)                 # ...even if it's not the rule fixpoint
    assert not task.is_agreed(PlanState(**{**ok.model_dump(), "salary": 120}))  # over band
    assert not task.is_agreed(PlanState(**{**ok.model_dump(), "bonus": 20}))    # over cap
    assert not task.is_agreed(PlanState(**{**ok.model_dump(), "remote": None})) # not signed


def test_story_ui_prompt_explainer_in_sync():
    """The scene-4 'why the same deal' explainer quotes the real prompts.
    Guard against drift: every role string and the user-prompt template shown
    in index.html must match the live Python source. Also enforce the naming
    convention: the pattern is 'blackboard', never 'whiteboard'."""
    html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "src", "ovb", "viz", "static", "index.html")
    with open(html_path, encoding="utf-8") as fh:
        html = fh.read()
    for src in agents.build_registry().sources:
        assert src.role in html, f"role for {src.name} missing/stale in index.html"
    assert ("Apply your constraint and report the single change you make "
            "(if any).") in html, "user-prompt template stale in index.html"
    assert "whiteboard" not in html.lower(), "naming: use 'blackboard', not 'whiteboard'"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all smoke tests passed")
