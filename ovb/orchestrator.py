"""ORCHESTRATOR — hub-and-spoke, supervisor-routed.

A central supervisor calls each sub-agent in a FIXED order. Sub-agents are
isolated: they never see each other, and every call is a fresh context window
(message-passing). Because there is no mid-task reaction, the only way to
resolve an interdependency is to sweep the whole roster again. The supervisor
repeats full sweeps until a sweep produces no change (convergence), capped by
``max_rounds``.

Cost signature: every round pays for ALL agents, including the ones a change
didn't touch — plus a final confirming sweep that changes nothing. That wasted
work is the price of a fixed hand-off order with no shared state.
"""
from __future__ import annotations

import time

from . import task
from .agents import build_agents
from .instrumentation import Recorder, latency_for

# Fixed supervisor routing order.
ORDER = ["Scope", "Budget", "Timeline", "Risk"]


def run(llm, real: bool = False, max_rounds: int = 10) -> dict:
    state = task.initial_state()
    agents = {a.name: a for a in build_agents()}
    rec = Recorder("orchestrator")

    rounds = 0
    for r in range(1, max_rounds + 1):
        rounds = r
        changed_any = False
        for name in ORDER:
            agent = agents[name]
            view = dict(state)  # fresh, isolated context handed out by the hub

            t0 = time.perf_counter()
            patch, _rationale, usage = agent.act(view, llm)
            measured = (time.perf_counter() - t0) * 1000.0

            for k, v in patch.items():
                rec.record_write(name, k, state.get(k), v)
                state[k] = v
            rec.record_call(name, usage, latency_for(usage, real, measured),
                            patch, trigger=f"sweep {r}")
            if patch:
                changed_any = True
        if not changed_any:
            break

    return {
        "engine": "orchestrator",
        "state": state,
        "recorder": rec,
        "rounds": rounds,
        "consistent": task.is_consistent(state),
    }
