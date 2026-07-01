"""LLM clients — one async interface, three implementations.

- MockLLM     : deterministic, offline, zero network. Synthetic token counts from
                real prompt length so the comparison is reproducible.
- ClaudeLLM   : real Anthropic **streaming** calls. Usage is reconciled correctly:
                `message_start` carries input + cache tokens; `message_delta`
                carries CUMULATIVE output tokens (we take the final value, never
                sum deltas). Lazy import so the base install stays light.
- CassetteLLM : wraps any client. Record mode captures (request -> text+usage) to
                disk keyed by a canonical request hash; replay mode serves those
                offline and deterministically. This is how real numbers become
                reproducible in CI with no key.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..contracts import Completion, Usage


def _est(text: str) -> int:
    return max(1, len(text) // 4)


def _req_key(*, model: str, system: str, prompt: str, temperature: float,
             max_tokens: int) -> str:
    canon = json.dumps(
        {"model": model, "system": system, "prompt": prompt,
         "temperature": temperature, "max_tokens": max_tokens},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(canon.encode()).hexdigest()


@runtime_checkable
class LLMClient(Protocol):
    name: str
    async def complete(self, *, system: str, prompt: str, expect: str = "",
                       tools=(), tools_exec=None) -> Completion: ...


class MockLLM:
    name = "mock"

    def __init__(self, model: str = "mock", temperature: float = 0.0,
                 max_tokens: int = 256):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def complete(self, *, system, prompt, expect="", tools=(),
                       tools_exec=None) -> Completion:
        text = expect or "ok"
        return Completion(
            text=text,
            usage=Usage(input_tokens=_est(system + prompt),
                        output_tokens=_est(text)),
        )


class ClaudeLLM:
    name = "claude"

    def __init__(self, model: str = "claude-sonnet-5", temperature: float = 0.0,
                 max_tokens: int = 256):
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise SystemExit("Real mode needs the SDK:  pip install anthropic") from exc
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def complete(self, *, system, prompt, expect="", tools=(),
                       tools_exec=None) -> Completion:
        text_parts: list[str] = []
        usage = Usage()
        async with self._client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for event in stream:
                if event.type == "message_start":
                    u = event.message.usage
                    usage = Usage(
                        input_tokens=u.input_tokens,
                        cache_creation_input_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
                        cache_read_input_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
                    )
                elif event.type == "text":
                    text_parts.append(event.text)
            final = await stream.get_final_message()
            # message_delta usage is CUMULATIVE — take the final, don't sum.
            usage = usage.model_copy(update={"output_tokens": final.usage.output_tokens})
        return Completion(text="".join(text_parts), usage=usage)


class CassetteLLM:
    """Record/replay around an inner client. Reproducible real numbers offline."""

    name = "cassette"

    def __init__(self, inner: LLMClient, path: str, *, mode: str = "replay",
                 model: str = "claude-sonnet-5", temperature: float = 0.0,
                 max_tokens: int = 256):
        self._inner = inner
        self._path = Path(path)
        self._mode = mode  # "record" | "replay"
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._store: dict[str, dict] = {}
        if self._path.exists():
            self._store = json.loads(self._path.read_text())

    async def complete(self, *, system, prompt, expect="", tools=(),
                       tools_exec=None) -> Completion:
        key = _req_key(model=self.model, system=system, prompt=prompt,
                       temperature=self.temperature, max_tokens=self.max_tokens)
        if self._mode == "replay":
            if key not in self._store:
                raise CassetteMiss(key, self._path)
            rec = self._store[key]
            return Completion(text=rec["text"], usage=Usage(**rec["usage"]))
        # record
        comp = await self._inner.complete(system=system, prompt=prompt,
                                          expect=expect, tools=tools,
                                          tools_exec=tools_exec)
        self._store[key] = {"text": comp.text, "usage": comp.usage.model_dump()}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._store, indent=2, sort_keys=True))
        return comp


class CassetteMiss(RuntimeError):
    def __init__(self, key: str, path: Path):
        super().__init__(f"cassette miss {key[:12]}… in {path}; re-record with `ovb record`")
        self.key = key
