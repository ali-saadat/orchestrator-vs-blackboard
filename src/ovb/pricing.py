"""Model pricing → real $ cost from a Usage vector.

Prices are USD per million tokens (list price). Cache WRITE (5-min TTL) is billed
at ~1.25× base input; cache READ at ~0.1× base input.

Source: Anthropic pricing page, observed 2026-07-01 (see docs/HARNESS.md → pricing).
Notable: Opus 4.8 is $5/$25 (older Opus 4.1 was $15/$75, retired). Sonnet 5 carries
an INTRODUCTORY $2/$10 rate through 2026-08-31, reverting to $3/$15 on 2026-09-01 —
we encode today's rate and note the reversion. Update in this one place.
"""
from __future__ import annotations

from .contracts import ModelPrice, Usage

# model id -> (input, output) per Mtok. Cache write/read derived as 1.25× / 0.1×.
_BASE: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),   # intro thru 2026-08-31; then (3.0, 15.0)
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-fable-5": (2.0, 10.0),
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
