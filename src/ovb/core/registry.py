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

    async def act(self, view, llm, tools_exec=None, free: bool = False) -> ActResult:
        """Deterministic decision (rule) + LLM narration/validation. The numeric
        patch is always the rule output; in real mode `comp.text` is the model's
        own words and the tokens are real. This purity — act returns a patch, the
        harness applies it — is what lets the identical agent run under a
        sequential sweep and a reactive event loop unchanged.

        With `free=True` (free-talk mode) the MODEL is the decision authority:
        the rule is bypassed, the model is asked for its next move, and the JSON
        tail of its reply becomes the patch. The ownership reducer and the
        deterministic gate still hold the guardrails — but the destination is
        now genuinely up to the negotiation."""
        if free:
            comp = await llm.complete(
                system=self.role,
                prompt=_decide_prompt(self, view),
                expect="",
                tools=self.tools,
                tools_exec=tools_exec,
            )
            patch = parse_free_patch(comp.text, self.owns)
            return ActResult(source=self.name, patch=patch, rationale=comp.text,
                             usage=comp.usage or Usage())
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


def _decide_prompt(src: KnowledgeSource, view) -> str:
    """Free-talk mode: the model must DECIDE, not narrate. Whole $k integers;
    a JSON object on the last line carries the move."""
    state = view.model_dump() if hasattr(view, "model_dump") else view
    return (
        f"Live negotiation state: {state}. You may change ONLY your own fields: "
        f"{list(src.owns)}. Decide your next move toward closing the deal — "
        "concede, hold, announce a limit, or accept. A deal only counts once "
        "every field is filled: if the two sides have met at one number and a "
        "field you own is still null, set it NOW to formally close your part. "
        "Endless tiny steps kill deals — when the gap is small, accept. "
        "Persuade in ONE short sentence, then end your reply with a single "
        'JSON object on its own line containing just the fields you change, '
        'e.g. {"ask": 120} — or {} to hold your position. Whole numbers only '
        "(amounts in $k)."
    )


_JSON_OBJ = None  # compiled lazily; keeps the import section unchanged


def parse_free_patch(text: str, owns: tuple[str, ...]) -> dict[str, int]:
    """Extract the model's move: the LAST {...} object in the reply, filtered to
    the fields this agent owns, values coerced to int. Anything malformed —
    no JSON, bad JSON, foreign fields, non-numeric values — degrades to
    'hold your position' ({}) rather than crashing the run."""
    global _JSON_OBJ
    import json
    import re
    if _JSON_OBJ is None:
        _JSON_OBJ = re.compile(r"\{[^{}]*\}")
    matches = _JSON_OBJ.findall(text or "")
    if not matches:
        return {}
    try:
        raw = json.loads(matches[-1])
    except (json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    patch: dict[str, int] = {}
    for k, v in raw.items():
        if k not in owns:
            continue
        try:
            patch[k] = int(round(float(v)))
        except (TypeError, ValueError):
            continue
    return patch


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
