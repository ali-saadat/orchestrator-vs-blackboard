"""KnowledgeSource (agent) abstraction + the shared registry.

A `KnowledgeSource` is the blackboard-literature term for a specialist agent: it
*owns* fields, *subscribes* to field changes, has a `role` (system prompt) and a
deterministic `rule` (the decision authority), and may declare `tools` for real
external-data tool-use.

The SAME registry instance is handed to all three harnesses — that is the
code-level fairness guarantee: identical roster, identical wiring. Its
`fingerprint` is checked by the FairnessContract.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from ..contracts import ActResult, Usage


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Awaitable[Any]]  # async external data


@dataclass(frozen=True)
class KnowledgeSource:
    name: str
    owns: tuple[str, ...]
    subscribes: tuple[str, ...]
    role: str                                   # system prompt persona (real mode)
    rule: Callable[[Any], dict[str, Any]]       # (state) -> patch  (decision authority)
    tools: tuple[ToolSpec, ...] = ()

    async def act(self, view, llm, tools_exec=None) -> ActResult:
        """Deterministic decision (rule) + LLM narration/validation. The numeric
        patch is always the rule output; in real mode `comp.text` is the model's
        own words and the tokens are real. This purity — act returns a patch, the
        harness applies it — is what lets the identical agent run under a
        sequential sweep and a reactive event loop unchanged."""
        patch = self.rule(view)
        rationale = _narrate(self.name, patch)
        comp = await llm.complete(
            system=self.role,
            prompt=_prompt(self, view),
            expect=rationale,
            tools=self.tools,
            tools_exec=tools_exec,
        )
        return ActResult(source=self.name, patch=patch, rationale=comp.text,
                         usage=comp.usage or Usage())


def _narrate(name: str, patch: dict) -> str:
    if not patch:
        return f"{name}: already consistent with my constraint; no change."
    parts = ", ".join(f"{k}->{v}" for k, v in patch.items())
    return f"{name}: adjusting {parts}."


def _prompt(src: KnowledgeSource, view) -> str:
    state = view.model_dump() if hasattr(view, "model_dump") else view
    return (f"Current plan state: {state}. You own {list(src.owns)}. "
            "Apply your constraint and report the single change you make (if any).")


@dataclass
class AgentRegistry:
    sources: tuple[KnowledgeSource, ...]

    def get(self, name: str) -> KnowledgeSource:
        for s in self.sources:
            if s.name == name:
                return s
        raise KeyError(name)

    def names(self) -> list[str]:
        return [s.name for s in self.sources]

    def subscription_index(self, only: set[str] | None = None) -> dict[str, list[str]]:
        """field -> [agent names triggered by a write to it]. `only` restricts to a
        subset of agents (used by the hybrid's bounded-blackboard core)."""
        idx: dict[str, list[str]] = defaultdict(list)
        for s in self.sources:
            if only is not None and s.name not in only:
                continue
            for f in s.subscribes:
                idx[f].append(s.name)
        return dict(idx)

    def fingerprint(self) -> str:
        spec = ";".join(
            f"{s.name}|owns={','.join(s.owns)}|subs={','.join(s.subscribes)}|role={s.role}"
            for s in self.sources
        )
        return hashlib.sha256(spec.encode()).hexdigest()[:16]
