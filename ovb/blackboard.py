"""BLACKBOARD — shared-state, event-driven.

All agents read/write ONE shared state. A control unit runs an event loop: when
a field changes, every agent that *subscribes* to that field is enqueued. Agents
therefore react mid-flight — only the ones affected by a change re-run, instead
of re-sweeping the whole roster.

Three ingredients keep it bounded and auditable (the "bounded blackboard" idea):
  * WORM log   — every write is appended via ``record_write`` for full audit.
  * gate       — a deterministic ``is_consistent`` check ends the run; the LLM
                 never decides "we're done".
  * control unit — ``max_steps`` caps iterations so a cascade can never run away.

Cost signature: work is proportional to the number of writes that actually
ripple, not to roster_size x rounds.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from . import task
from .agents import build_agents
from .instrumentation import Recorder, latency_for


def run(llm, real: bool = False, max_steps: int = 100) -> dict:
    state = task.initial_state()
    agents = {a.name: a for a in build_agents()}
    rec = Recorder("blackboard")

    # subscription index: field -> [agent names triggered by a write to it]
    subs = defaultdict(list)
    for a in agents.values():
        for f in a.subscribes:
            subs[f].append(a.name)

    queue: deque = deque()
    queued: set = set()

    def enqueue(names, why):
        for n in names:
            if n not in queued:
                queue.append((n, why))
                queued.add(n)

    # seed: the external requirement lands on the board as scope=8, which wakes
    # every agent subscribed to `scope`.
    enqueue(subs.get("scope", []), "seed: scope posted")

    steps = 0
    while queue and steps < max_steps:   # control unit caps iterations
        steps += 1
        name, why = queue.popleft()
        queued.discard(name)
        agent = agents[name]

        view = dict(state)
        t0 = time.perf_counter()
        patch, _rationale, usage = agent.act(view, llm)
        measured = (time.perf_counter() - t0) * 1000.0

        for k, v in patch.items():
            rec.record_write(name, k, state.get(k), v)
            state[k] = v
            enqueue(subs.get(k, []), f"{k} changed")   # ripple to dependents

        rec.record_call(name, usage, latency_for(usage, real, measured),
                        patch, trigger=why)

        if task.is_consistent(state):   # the gate — deterministic, not the LLM
            break

    return {
        "engine": "blackboard",
        "state": state,
        "recorder": rec,
        "steps": steps,
        "consistent": task.is_consistent(state),
    }
