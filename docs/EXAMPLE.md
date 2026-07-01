# Worked example — real Claude calls, three harnesses, four models

Real runs of all three harness topologies on the reconciliation task
(`features=8, budget=90`) using **live streaming Claude** across four models. Every
call was recorded to [`../cassettes/demo.json`](../cassettes/demo.json), so you can
**replay these exact real numbers offline, with no API key**:

```bash
ovb models                                 # the table below, from the cassette
ovb bench --cassette cassettes/demo.json   # one model (default: cheapest, Haiku 4.5)
ovb serve   # dashboard → mode=Cassette, pick a model
```

## Two independent axes — read them separately

**Axis 1 — control model (the harness).** Within any single model, the blackboard and
hybrid converge in fewer calls/tokens than the orchestrator, because they re-trigger only
the affected agents instead of re-sweeping the whole roster. Blackboard = **1.71× fewer
calls** than orchestrator; hybrid fewer still.

**Axis 2 — the LLM model.** Because the agents' decisions come from **deterministic rules**
(the model only *narrates*), the model choice does **not** change the plan or the call
counts — **only the narration tokens and cost**. So pick the cheapest model that fits.

## Real numbers (recorded, replayable offline)

| Model | $/Mtok in/out | calls (orch/bb/hyb) | tokens (orch/bb/hyb) | cost USD (orch/bb/hyb) |
|---|---|---|---|---|
| **Haiku 4.5** ★ cheapest | 1 / 5 | 12 / 7 / 5 | 3669 / 2158 / 1492 | **$0.0141 / $0.0083 / $0.0057** |
| Sonnet 5 | 2 / 10 | 12 / 7 / 5 | 4366 / 2602 / 1775 | $0.0325 / $0.0195 / $0.0132 |
| Opus 4.8 | 5 / 25 | 12 / 7 / 5 | 4458 / 2596 / 1705 | $0.0836 / $0.0487 / $0.0312 |
| Fable 5 | 10 / 50 | 12 / 7 / 5 | 4425 / 2598 / 1822 | $0.1656 / $0.0975 / $0.0682 |

**Every model reaches the identical plan** (`scope 6 · $90k · 12 wk · risk medium`) and the
**identical 12/7/5 call counts**. The only thing that moves is cost — a **~20× spread**
(Haiku blackboard $0.0083 → Fable orchestrator $0.166) for the *same outcome*.

### What to flag
- **Use the cheapest model that fits: Haiku 4.5 ($1/$5).** For this narration workload it is
  the correct default — nothing cheaper is on the direct API (Haiku 3.5 at $0.80/$4 is retired
  to Bedrock/Vertex only). Haiku 4.5 also avoids the newer tokenizer's ~30% token inflation
  that Opus 4.7+/Sonnet 5/Fable 5 add.
- **Fable 5 ($10/$50) is overkill** — a general flagship (2× Opus), built for demanding
  long-horizon reasoning, not narration. Its always-on thinking inflates output tokens too.
- **Streaming, not batch.** We use the streaming Messages API (real-time SSE, so you see the
  flow). The Batch API is 50% cheaper but asynchronous (up to 24h) and cannot stream — wrong
  for a live UI.

## Reproduce with your own key

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env      # .env is gitignored — never commit it
ovb bench --real                                # default model = Haiku 4.5 (cheapest)
ovb models --real                               # compare models live
ovb bench --real --model claude-opus-4-8 --cassette cassettes/demo.json   # (re)record a model
```

Notes: `temperature` is not sent (reasoning models deprecate it). Replay wall-time is synthetic;
tokens and cost are the real recorded values. Open [`examples/report.html`](../examples/report.html)
for the animated report generated from the cassette.
