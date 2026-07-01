"""The four specialists as KnowledgeSources — IDENTICAL for all three harnesses.

Gaming-PC build. Rules close over `ScenarioParams`. Each `rule` is the
deterministic decision authority; the LLM narrates/validates.
  - GPU         owns `gpu`,   reacts to `max_gpu`  (drop the tier if the budget won't allow it)
  - Budget      owns `cost`+`max_gpu`, reacts to `gpu`  (price it; cap the tier)
  - Power       owns `watts`, reacts to `gpu`
  - Performance owns `perf`,  reacts to `gpu`, `watts`
"""
from __future__ import annotations

from ..core.registry import AgentRegistry, KnowledgeSource
from . import task
from .task import ScenarioParams


def build_registry(params: "ScenarioParams | None" = None) -> AgentRegistry:
    p = params or ScenarioParams()

    def gpu_rule(s):
        if s.max_gpu is not None and s.gpu > s.max_gpu:
            return {"gpu": s.max_gpu}
        return {}

    def budget_rule(s):
        cost = s.gpu * p.gpu_price
        patch = {"cost": cost}
        if cost > p.budget_cap:
            patch["max_gpu"] = p.budget_cap // p.gpu_price
        else:
            patch["max_gpu"] = s.gpu
        return patch

    def power_rule(s):
        return {"watts": task.watts_for(s.gpu, p)}

    def perf_rule(s):
        return {"perf": task.perf_for(s.gpu)}

    return AgentRegistry(
        sources=(
            KnowledgeSource(
                "GPU", ("gpu",), ("max_gpu",),
                "You own the GPU tier. Keep it within the tier the budget allows.",
                gpu_rule,
            ),
            KnowledgeSource(
                "Budget", ("cost", "max_gpu"), ("gpu",),
                "You own the Budget. Price the build and cap the affordable GPU tier.",
                budget_rule,
            ),
            KnowledgeSource(
                "Power", ("watts",), ("gpu",),
                "You own the PSU. Wattage scales with the GPU tier.",
                power_rule,
            ),
            KnowledgeSource(
                "Performance", ("perf",), ("gpu", "watts"),
                "You own Performance. The FPS class follows the GPU tier.",
                perf_rule,
            ),
        )
    )
