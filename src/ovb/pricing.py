"""Model pricing → real $ cost from a Usage vector.

Prices are USD per million tokens (list price). Cache WRITE (5-min TTL) is billed
at ~1.25× base input; cache READ at ~0.1× base input.

Source: Anthropic pricing page, observed 2026-07-01 (see docs/HARNESS.md → pricing).
Notable:
- Haiku 4.5 ($1/$5) is the CHEAPEST generally-available first-party model. (Haiku 3.5
  is nominally $0.80/$4 but is RETIRED — Bedrock/Vertex only, not the direct API.)
- Sonnet 5 carries an INTRODUCTORY $2/$10 rate through 2026-08-31, then $3/$15.
- Opus 4.8 is $5/$25 (older Opus 4.1 was $15/$75, retired).
- Fable 5 is $10/$50 — a general-capability flagship (2× Opus), NOT a writing model;
  it also uses the newer tokenizer (~30% more tokens) and always-on thinking.
Update in this one place.
"""
from __future__ import annotations

from .contracts import ModelPrice, Usage

# model id -> (input, output) per Mtok. Cache write/read derived as 1.25× / 0.1×.
_BASE: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.0, 50.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),   # intro thru 2026-08-31; then (3.0, 15.0)
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),   # cheapest
}
_DEFAULT = "claude-sonnet-5"


def get_price(model: str) -> ModelPrice:
    base_in, base_out = _BASE.get(model, _BASE[_DEFAULT])
    return ModelPrice(
        model=model,
        input_per_mtok=base_in,
        output_per_mtok=base_out,
        cache_write_per_mtok=round(base_in * 1.25, 4),
        cache_read_per_mtok=round(base_in * 0.10, 4),
    )


def is_known(model: str) -> bool:
    return model in _BASE


def cost_of(usage: Usage, model: str) -> float:
    return usage.cost_usd(get_price(model))
