"""Amazon Bedrock backend — one Converse client across model families.

This lets the same negotiation harness run over Anthropic, Amazon Nova, Meta
Llama, Mistral, and DeepSeek models behind a single API, so a cross-provider /
cross-scale / reasoning-vs-not comparison uses identical prompts and gate.

The roster below is the experimental design: each entry tags a family, a size
tier (nano/small/medium/large), and whether it is a reasoning model. Logical
names (e.g. ``nova-micro``) are used everywhere in the harness; this module maps
them to Bedrock model IDs and handics the cross-region inference-profile prefix.
"""
from __future__ import annotations

import asyncio
import json as _json

from ..contracts import Completion, Usage

# logical name -> dict(id, family, tier, reasoning, price=(in,out) per Mtok approx)
ROSTER: dict[str, dict] = {
    # --- Amazon Nova: clean nano/flash/medium tiers, one family ---
    "nova-micro":   {"id": "amazon.nova-micro-v1:0", "family": "amazon", "tier": "nano",   "reasoning": False, "price": (0.035, 0.14)},
    "nova-lite":    {"id": "amazon.nova-lite-v1:0",  "family": "amazon", "tier": "small",  "reasoning": False, "price": (0.06, 0.24)},
    "nova-pro":     {"id": "amazon.nova-pro-v1:0",   "family": "amazon", "tier": "medium", "reasoning": False, "price": (0.80, 3.20)},
    # --- Meta Llama: open-weights, independent of the proprietary vendors ---
    "llama-3b":     {"id": "us.meta.llama3-2-3b-instruct-v1:0",  "family": "meta", "tier": "nano",   "reasoning": False, "price": (0.15, 0.15)},
    "llama-8b":     {"id": "us.meta.llama3-1-8b-instruct-v1:0",  "family": "meta", "tier": "small",  "reasoning": False, "price": (0.22, 0.22)},
    "llama-70b":    {"id": "us.meta.llama3-3-70b-instruct-v1:0", "family": "meta", "tier": "medium", "reasoning": False, "price": (0.72, 0.72)},
    # --- Mistral: European open-weights + a reasoning model (magistral) ---
    "ministral-3b": {"id": "mistral.ministral-3-3b-instruct",   "family": "mistral", "tier": "nano",   "reasoning": False, "price": (0.04, 0.04)},
    "ministral-8b": {"id": "mistral.ministral-3-8b-instruct",   "family": "mistral", "tier": "small",  "reasoning": False, "price": (0.10, 0.10)},
    "magistral":    {"id": "mistral.magistral-small-2509",      "family": "mistral", "tier": "medium", "reasoning": True,  "price": (0.50, 1.50)},
    # --- DeepSeek: the reasoning/non-reasoning contrast within one family ---
    "deepseek-r1":  {"id": "us.deepseek.r1-v1:0", "family": "deepseek", "tier": "large", "reasoning": True,  "price": (1.35, 5.40)},
    "deepseek-v3":  {"id": "us.deepseek.v3.2",    "family": "deepseek", "tier": "large", "reasoning": False, "price": (0.58, 1.68)},
    # --- Anthropic via Bedrock (same family as the earlier direct-API runs) ---
    "claude-haiku": {"id": "us.anthropic.claude-haiku-4-5-20251001-v1:0", "family": "anthropic", "tier": "small",  "reasoning": False, "price": (1.0, 5.0)},
    "claude-sonnet":{"id": "us.anthropic.claude-sonnet-5-v1:0",           "family": "anthropic", "tier": "medium", "reasoning": False, "price": (2.0, 10.0)},
}


def bedrock_price(name: str):
    e = ROSTER.get(name)
    return e["price"] if e else None


class BedrockLLM:
    name = "bedrock"

    def __init__(self, model: str, temperature: float = 0.0, max_tokens: int = 256,
                 region: str = "us-east-1", profile: str = "dugun"):
        import boto3
        self._client = boto3.Session(profile_name=profile, region_name=region) \
            .client("bedrock-runtime")
        self.logical = model
        self.entry = ROSTER.get(model)
        if not self.entry:
            raise ValueError(f"unknown Bedrock model '{model}'; see ROSTER")
        self._id = self.entry["id"]
        self.temperature = temperature
        self.reasoning = self.entry["reasoning"]
        # reasoning models spend tokens on a trace before the answer — give room
        self.max_tokens = max(max_tokens, 3072) if self.reasoning else max_tokens

    async def complete(self, *, system, prompt, expect="", tools=(), tools_exec=None) -> Completion:
        return await asyncio.to_thread(self._call, system, prompt)

    def _call(self, system, prompt) -> Completion:
        infcfg = {"maxTokens": self.max_tokens}
        if not self.reasoning:              # reasoning models manage their own sampling
            infcfg["temperature"] = self.temperature
        kw = dict(modelId=self._id,
                  messages=[{"role": "user", "content": [{"text": prompt}]}],
                  inferenceConfig=infcfg)
        if system:
            kw["system"] = [{"text": system}]
        last = None
        for attempt in range(4):
            try:
                r = self._client.converse(**kw)
                blocks = r["output"]["message"]["content"]
                text = "".join(b.get("text", "") for b in blocks if "text" in b)
                u = r.get("usage", {})
                return Completion(text=text, usage=Usage(
                    input_tokens=u.get("inputTokens", 0),
                    output_tokens=u.get("outputTokens", 0)))
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                last = exc
                # some models are only reachable via a cross-region inference profile
                if ("inference profile" in msg or "on-demand throughput is" in msg) \
                        and not kw["modelId"].startswith("us."):
                    kw["modelId"] = "us." + kw["modelId"]
                    continue
                # some models reject a system block — fold it into the user turn
                if "system" in kw and ("system" in msg.lower() and "not" in msg.lower()):
                    kw["messages"][0]["content"][0]["text"] = (system + "\n\n" + prompt)
                    kw.pop("system")
                    continue
                if "ThrottlingException" in msg or "TooManyRequests" in msg:
                    import time
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break
        raise RuntimeError(f"Bedrock converse failed for {self._id}: {last}")
