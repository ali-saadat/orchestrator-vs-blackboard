# Worked example — real Claude calls, three harnesses, three models

Real runs of all three harness topologies on the **gaming-PC build** task
(`gpu=4, budget=1000`) using **live streaming Claude** across three models. Every
call was recorded to [`../cassettes/demo.json`](../cassettes/demo.json), so you can
**replay these exact real numbers offline, with no API key**:

```bash
ovb models                                 # the table below, from the cassette
ovb bench --cassette cassettes/demo.json   # one model (default: cheapest, Haiku 4.5)
ovb serve   # dashboard → mode = Cassette, pick a model
```

## The task

Four specialists spec one gaming PC: **GPU** (you want tier 4), **Budget** (hard cap
$1000, $300/tier → tier 3 max), **Power** (PSU watts = tier×150+100), **Performance**
(FPS class from the tier). The GPU tier drives everything, so dropping it to fit the
budget also drops the wattage and FPS — a change ripples, but only to the agents that
depend on the tier. All three harnesses reach the identical build: **tier 3 · $900 ·
550W · high**.

## Two independent axes — read them separately

**Axis 1 — control model (the harness).** Within any model, the blackboard/hybrid
converge in fewer calls because they re-trigger only the affected agents instead of
re-sweeping all four. Blackboard = **1.71× fewer calls** than the orchestrator.

**Axis 2 — the LLM model.** Decisions are **rule-based** (the model only narrates), so
the model choice never changes the build or the call counts — **only tokens and cost**.

## Real numbers (recorded, replayable offline)

| Model | $/Mtok in/out | calls (orch/bb/hyb) | tokens (orch/bb/hyb) | cost USD (orch/bb/hyb) |
|---|---|---|---|---|
| **Haiku 4.5** ★ cheapest | 1 / 5 | 12 / 7 / 5 | 2988 / 1863 / 1367 | **$0.0108 / $0.0069 / $0.0051** |
| Sonnet 5 | 2 / 10 | 12 / 7 / 5 | 4106 / 2438 / 1729 | $0.0305 / $0.0182 / $0.0130 |
| Opus 4.8 | 5 / 25 | 12 / 7 / 5 | 4095 / 2416 / 1646 | $0.0761 / $0.0450 / $0.0303 |

**Every model reaches the identical build** (`tier 3 · $900 · 550W · high`) and the
**identical 12/7/5 call counts**. Only cost moves — a ~15× spread (Haiku hybrid $0.0051
→ Opus orchestrator $0.076) for the same outcome.

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
ovb bench --real --gpu 3 --budget 700 --cassette cassettes/demo.json   # record another prompt
```

Notes: `temperature` is not sent (reasoning models deprecate it). Replay wall-time is
synthetic; tokens and cost are the real recorded values. Open
[`examples/report.html`](../examples/report.html) for the animated report from the cassette.
