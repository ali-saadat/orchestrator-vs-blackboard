# Worked example — real Claude calls, three harnesses, three models

Real runs of all three harness topologies on the **birthday-party** task
(`guests=15, budget=600`) using **live streaming Claude** across three models. Every
call was recorded to [`../cassettes/demo.json`](../cassettes/demo.json), so you can
**replay these exact real numbers offline, with no API key**:

```bash
ovb models                                 # the table below, from the cassette
ovb bench --cassette cassettes/demo.json   # one model (default: cheapest, Haiku 4.5)
ovb serve   # dashboard → mode = Cassette, pick a model
```

## The task

Four friends plan one birthday party: **Guests** (you'd love 15), **Budget** (hard cap
$600 at $50/head all-in → 12 max), **Food** (one pizza feeds 3), **Chairs** (one chair
per guest). The guest list drives everything, so trimming it to fit the budget also
shrinks the pizza order and the chair count — a change ripples, but only to the friends
who depend on the headcount. All three harnesses reach the identical plan:
**12 guests · $600 · 4 pizzas · 12 chairs**.

## Two independent axes — read them separately

**Axis 1 — control model (the harness).** Within any model, the blackboard/hybrid
converge in fewer calls because they re-trigger only the affected agents instead of
re-sweeping all four. Blackboard = **1.71× fewer calls** than the orchestrator.

**Axis 2 — the LLM model.** Decisions are **rule-based** (the model only narrates), so
the model choice never changes the plan or the call counts — **only tokens and cost**.

## Real numbers (recorded, replayable offline)

| Model | $/Mtok in/out | calls (orch/bb/hyb) | tokens (orch/bb/hyb) | cost USD (orch/bb/hyb) |
|---|---|---|---|---|
| **Haiku 4.5** ★ cheapest | 1 / 5 | 12 / 7 / 5 | 2678 / 1494 / 947 | **$0.0094 / $0.0051 / $0.0031** |
| Sonnet 5 | 2 / 10 | 12 / 7 / 5 | 3970 / 2442 / 1638 | $0.0295 / $0.0184 / $0.0121 |
| Opus 4.8 | 5 / 25 | 12 / 7 / 5 | 3646 / 2216 / 1570 | $0.0656 / $0.0405 / $0.0286 |

**Every model reaches the identical plan** (`12 guests · $600 · 4 pizzas · 12 chairs`) and
the **identical 12/7/5 call counts**. Only cost moves — a ~21× spread (Haiku hybrid
$0.0031 → Opus orchestrator $0.066) for the same outcome.

### What to flag
- **Use the cheapest model that fits: Haiku 4.5 ($1/$5).** For a narration workload it's
  the right default (nothing cheaper is on the direct API; it also avoids the newer
  tokenizer's ~30% token inflation).
- **Streaming, not batch.** We use the streaming Messages API (real-time SSE, so you see
  the flow). The Batch API is 50% cheaper but async (up to 24h) and can't stream.
- Fable 5 ($10/$50) is available via `ovb models --models …,claude-fable-5` but isn't in
  the committed cassette (slow, and overkill for narration).

## Reproduce with your own key

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env      # .env is gitignored — never commit it
ovb bench --real                                # default model = Haiku 4.5 (cheapest)
ovb models --real                               # compare models live
ovb bench --real --guests 9 --budget 500 --cassette cassettes/demo.json   # record another ask
```

Notes: `temperature` is not sent (reasoning models deprecate it). Replay wall-time is
synthetic; tokens and cost are the real recorded values. Open
[`examples/report.html`](../examples/report.html) for the animated report from the cassette.
