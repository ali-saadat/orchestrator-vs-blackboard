# Worked example — real Claude calls, three harnesses, three models

Real runs of all three harness topologies on the **job-offer negotiation**
(`ask=130, band=110`) using **live streaming Claude** across three models. Every
call was recorded to [`../cassettes/demo.json`](../cassettes/demo.json), so you can
**replay these exact real numbers offline, with no API key**:

```bash
ovb models                                 # the table below, from the cassette
ovb bench --cassette cassettes/demo.json   # one model (default: cheapest, Haiku 4.5)
ovb serve   # dashboard → mode = Cassette, pick a model
```

## The task

Four people negotiate one job offer: the **Candidate** (asks $130k) and the **Manager**
(offers $100k) concede ~15% of the gap per turn; **HR** announces the hard band ($110k)
mid-talk — re-anchoring both — and grants remote days for the concession; **Finance**
caps salary+bonus ($124k) and signs the bonus once the base lands. A genuine multi-round
negotiation whose destination is provably unique: all three harnesses reach the identical
deal — **$110k + $8k bonus + 4 remote days**.

## Two independent axes — read them separately

**Axis 1 — control model (the harness).** Within any model, the blackboard/hybrid
converge in fewer calls because they re-trigger only the affected agents instead of
re-sweeping all four. Blackboard = **1.71× fewer calls** than the orchestrator (14 vs 24), with zero wasted turns vs 10.

**Axis 2 — the LLM model.** Decisions are **rule-based** (the model only narrates), so
the model choice never changes the plan or the call counts — **only tokens and cost**.

## Real numbers (recorded, replayable offline)

| Model | $/Mtok in/out | calls (orch/bb/hyb) | tokens (orch/bb/hyb) | cost USD (orch/bb/hyb) |
|---|---|---|---|---|
| **Haiku 4.5** ★ cheapest | 1 / 5 | 24 / 14 / 13 | 8464 / 4875 / 4123 | **$0.0312 / $0.0181 / $0.0148** |
| Sonnet 5 | 2 / 10 | 24 / 14 / 13 | 9554 / 5536 / 5124 | $0.0683 / $0.0397 / $0.0369 |
| Opus 4.8 | 5 / 25 | 24 / 14 / 13 | 9209 / 5205 / 4798 | $0.1620 / $0.0911 / $0.0840 |

**Every model reaches the identical deal** (`$110k + $8k bonus · 4d remote`) and the
**identical 24/14/13 call counts**. Only cost moves — a ~11× spread (Haiku hybrid
$0.0148 → Opus orchestrator $0.162) for the same outcome.

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
ovb bench --real --ask 120 --band 105 --cassette cassettes/demo.json      # record another ask
```

Notes: `temperature` is not sent (reasoning models deprecate it). Replay wall-time is
synthetic; tokens and cost are the real recorded values. Open
[`examples/report.html`](../examples/report.html) for the animated report from the cassette.
