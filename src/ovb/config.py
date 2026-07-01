"""Run configuration — the single source of the fairness-critical parameters.

`model` and `temperature` live here so NO engine can silently sample differently;
the FairnessContract fingerprints these and hard-fails if they diverge across a
comparison. Env override via the `OVB_` prefix (e.g. `OVB_MODEL=claude-opus-4-8`).
"""
from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict


class RunConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    # provider / sampling (fairness-critical: identical across all engines).
    # Default to the CHEAPEST model: since agent decisions are rule-based, the model
    # only narrates — model choice changes tokens/cost, never the plan or call counts.
    model: str = "claude-haiku-4-5-20251001"
    temperature: float = 0.0
    max_tokens: int = 256

    # execution mode
    real: bool = False              # False = MockLLM (deterministic, offline)
    cassette: str | None = None     # path to a cassette for record/replay

    # control-loop bounds (the control unit's safety caps)
    max_rounds: int = 12            # orchestrator: max full sweeps
    max_steps: int = 100            # blackboard: max event-loop steps
    hybrid_cap: int = 50            # hybrid: max steps in the bounded-blackboard core

    # fair, honest reporting knobs
    orch_early_exit: bool = False   # give the orchestrator the SAME gate early-exit (reported as a variant)
    n_runs: int = 1                 # >1 => variance over repeated real runs (temp=0)

    # live-view pacing: seconds to pause per harness step so a human can watch the
    # control loop unfold. 0 in mock/CI (instant); real mode is paced by LLM latency.
    step_delay: float = 0.0

    @classmethod
    def from_env(cls, **overrides) -> "RunConfig":
        env = {}
        for field in cls.model_fields:
            key = f"OVB_{field.upper()}"
            if key in os.environ:
                env[field] = os.environ[key]
        return cls(**{**env, **overrides})
