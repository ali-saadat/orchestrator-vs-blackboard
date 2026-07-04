"""The Harness — the shared control-loop substrate.

This is the heart of the repo's thesis. An agent harness is the deterministic
program around the model that owns: the control loop, context assembly, tool
dispatch, error handling, and the termination gate (see docs/HARNESS.md).

`Harness` implements those responsibilities ONCE:

  * `invoke(source, trigger)` — the single unit of agent execution ("one harness
    step"): assemble the view, call the model, apply the validated patch through
    the ownership reducer, and record every token/write/cost.
  * `gate_passed()` — the deterministic termination check.

Orchestrator, Blackboard, and Hybrid subclass this and implement ONLY `run()` —
i.e. only the *scheduling discipline*. Same primitives, different control model.
That is exactly why they are a fair comparison and a clean illustration of "three
harness topologies over identical agents."
"""
from __future__ import annotations

import asyncio
import time

from ..contracts import EngineResult, Sequencer
from ..pricing import get_price
from .gate import Gate
from .registry import AgentRegistry, KnowledgeSource
from .state import apply_patch
from .trace import Recorder


class Harness:
    control_model: str = "abstract"

    def __init__(self, *, registry: AgentRegistry, gate: Gate, initial_state,
                 llm, config, run_id: str, sequencer: Sequencer, scenario: str,
                 tools_exec=None, event_sink=None):
        self.registry = registry
        self.gate = gate
        self.state = initial_state
        self.llm = llm
        self.config = config
        self.run_id = run_id
        self.scenario = scenario
        self.tools_exec = tools_exec
        self._price = get_price(config.model)
        self.rec = Recorder(self.control_model, run_id, sequencer, config.model,
                            on_event=event_sink)
        # free-talk transcript: the agents' recent WORDS (not just numbers), so
        # they can actually argue and convince each other. Only the numbers are
        # state; the talk is context. Unused (empty) under hard rules.
        self.talk: list[str] = []

    # ---- shared harness primitives -----------------------------------------
    async def invoke(self, source: KnowledgeSource, *, trigger: str) -> dict:
        """One harness step. Returns the dict of fields that changed."""
        self.rec.agent_activated(source.name, trigger)
        view = self.state
        self.rec.llm_call_started(source.name)
        if self.config.step_delay:      # pacing so a human can watch it think
            await asyncio.sleep(self.config.step_delay)
        t0 = time.perf_counter()
        result = await source.act(view, self.llm, self.tools_exec,
                                  free=self.config.free,
                                  talk=tuple(self.talk[-6:]))
        measured_ms = (time.perf_counter() - t0) * 1000.0

        new_state, changes = apply_patch(
            self.state, result.patch, owner=source.name, owns=source.owns
        )
        self.state = new_state
        for field, (old, new) in changes.items():
            self.rec.state_write(source.name, field, old, new)

        if self.config.free and result.rationale:
            from .registry import talk_line
            line = talk_line(source.name, result.rationale)
            if line:
                self.talk.append(line)

        cost = result.usage.cost_usd(self._price)
        latency = measured_ms if self.config.real else result.usage.total / 10.0
        self.rec.call_finished(source.name, result.usage, cost, latency,
                               changes, trigger, message=result.rationale)
        return changes

    def gate_passed(self) -> bool:
        passed = self.gate.passed(self.state)
        self.rec.gate_checked(passed)
        return passed

    # ---- per-topology scheduling (subclasses implement) --------------------
    async def run(self) -> EngineResult:  # pragma: no cover - abstract
        raise NotImplementedError

    def _finish(self, steps: int) -> EngineResult:
        state = self.state.model_dump()
        consistent = self.gate.passed(self.state)
        self.rec.run_finished(state, consistent)
        return EngineResult(control_model=self.control_model, state=state,
                            consistent=consistent, steps=steps, recorder=self.rec)

    def _start(self) -> None:
        self.rec.run_started(self.scenario)
