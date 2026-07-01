# Worked example — real Claude calls, three harnesses, one prompt

This is a real run of all three harness topologies on the reconciliation task
(`features=8, budget=90`) using **live streaming Claude (`claude-sonnet-5`)**. The
calls were recorded to [`../cassettes/demo.json`](../cassettes/demo.json), so you can
**replay these exact real numbers offline, with no API key**.

## Real results

| Harness | Calls | Wasted | Tokens | Cost (USD) | Wall time | Final plan |
|---|---|---|---|---|---|---|
| Orchestrator | 12 | 5 | 4,366 | $0.0325 | ~46 s | scope 6 · $90k · 12 wk · medium |
| Blackboard | 7 | 0 | 2,602 | $0.0195 | ~27 s | *identical* |
| Hybrid | 5 | 0 | 1,775 | $0.0132 | ~19 s | *identical* |

All three reach the **same** consistent plan. The blackboard uses **1.71× fewer calls**
and **1.68× fewer tokens** than the orchestrator; the hybrid, by exploiting the
Scope↔Budget dependency structure, uses fewer still. The margins hold with real tokens,
not just the mock estimate — and the token *ratio* is a property of the control model.

Real narration is meaningful — e.g. the blackboard's Scope agent:

> **Change applied:** Reduce `scope` from 8 → 6. **Rationale:** the plan shows `scope: 8`
> against a `max_scope` of 6 — a violation of 2 units over budget. As the Scope owner my
> constraint is to keep scope ≤ max_scope, so I cut to 6 …

(The numeric decision is still the deterministic rule; the model narrates and the tokens
are real. See [PLAN.md](PLAN.md) §12 for why we separate the two.)

## Reproduce it

**Replay the recorded real numbers — offline, no key (this is the committed example):**

```bash
ovb bench --cassette cassettes/demo.json          # CLI table
ovb serve         # then choose mode = "Cassette" in the dashboard
```

Open [`examples/report.html`](../examples/report.html) for the self-contained animated
report generated from the cassette.

**Record your own with a live key:**

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env         # .env is gitignored — never commit it
ovb bench --real                                   # live streaming calls
ovb bench --real --cassette cassettes/demo.json    # (re)record the cassette
ovb serve         # then choose mode = "Real API"
```

Notes:
- `temperature` is intentionally not sent — the flagship reasoning models
  (`claude-sonnet-5`) deprecate it; real-run reproducibility comes from the cassette.
- Wall time in replay is synthetic (instant); the table above shows the *recorded* real
  wall time. Tokens and cost are the real recorded values in both cases.
