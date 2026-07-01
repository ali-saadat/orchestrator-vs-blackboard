"""LLM abstraction shared by BOTH control models.

The whole point of this repo is that the *agents* and the *LLM* are identical
across the orchestrator and the blackboard — only the control model differs.
So the LLM lives here, exactly once.

- MockLLM   : deterministic, zero-dependency, offline. The default.
- ClaudeLLM : real Anthropic API calls (`pip install anthropic`, set
              ANTHROPIC_API_KEY). Enabled with `--real`.

Both return a ``Completion(text, usage)`` where ``usage`` carries token counts,
so the instrumentation layer can compare cost across the two topologies.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.prompt_tokens + other.prompt_tokens,
            self.completion_tokens + other.completion_tokens,
        )


@dataclass
class Completion:
    text: str
    usage: Usage


def estimate_tokens(text: str) -> int:
    """~4 chars per token — the usual rough rule for English BPE tokenizers."""
    return max(1, len(text) // 4)


class MockLLM:
    """Deterministic stand-in for a real model.

    It does NOT do any reasoning — the *agents* carry the decision rules (see
    ``agents.py``). The MockLLM exists so that (a) the code path is identical to
    real mode and (b) every call gets a realistic *synthetic* token count derived
    from the actual prompt length. That makes the token comparison between the
    two topologies meaningful and fully reproducible.
    """

    name = "mock"

    def complete(self, system: str, prompt: str, expect: str = "") -> Completion:
        text = expect or "ok"
        return Completion(
            text=text,
            usage=Usage(
                prompt_tokens=estimate_tokens(system + prompt),
                completion_tokens=estimate_tokens(text),
            ),
        )


class ClaudeLLM:
    """Real Claude calls. Kept deliberately thin.

    In real mode the agent still validates the model's decision against its rule
    (see ``agents.py``), so the two topologies stay comparable — the model
    narrates and reasons, but can't send the plan off the rails.
    """

    name = "claude"

    def __init__(self, model: str = "claude-sonnet-5"):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - only hit without the SDK
            raise SystemExit(
                "Real mode needs the anthropic SDK:  pip install anthropic"
            ) from exc
        self._client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._model = model

    def complete(self, system: str, prompt: str, expect: str = "") -> Completion:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=256,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            b.text for b in msg.content if getattr(b, "type", "") == "text"
        )
        return Completion(
            text=text,
            usage=Usage(
                prompt_tokens=msg.usage.input_tokens,
                completion_tokens=msg.usage.output_tokens,
            ),
        )


def get_llm(real: bool = False, model: str = "claude-sonnet-5"):
    return ClaudeLLM(model=model) if real else MockLLM()
