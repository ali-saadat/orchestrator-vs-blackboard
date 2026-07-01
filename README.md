# ovb — Orchestrator vs Blackboard vs Hybrid

**Three agent-*harness* topologies over the same agents, the same task, and the same
deterministic gate. Only the control loop differs — and it's all measured.**

A multi-agent system is `agents + a harness`: the agents are *model + role + tools*;
the **harness** is the deterministic program that owns the control loop, context
assembly, tool dispatch, and the termination gate. Orchestrator, blackboard, and
hybrid are three *harness topologies* — three answers to *how the harness schedules
model calls and where shared state lives*. This repo holds the agents constant and
swaps the harness, then instruments calls, tokens, cost, latency, and a full WORM
audit log so the difference is a number, not an opinion.

![Orchestrator vs Blackboard](docs/images/topologies.svg)

> New here? Read **[docs/HARNESS.md](docs/HARNESS.md)** for the organizing idea, then
> **[docs/WHEN-TO-USE.md](docs/WHEN-TO-USE.md)** to choose one for your own problem.

## Quickstart (mock mode — deterministic, offline, no API key)

```bash
pip install -e ".[dev]"          # or: export PYTHONPATH=src
ovb serve                        # ⭐ LIVE side-by-side dashboard in your browser
ovb bench                        # all 3 harnesses + comparison + output/report.html
ovb run blackboard               # one harness, print its trace
make test                        # deterministic checks
ovb doctor                       # what mode am I in?
```

Real model behavior and real token/cost numbers:

```bash
pip install -e ".[real]"
export ANTHROPIC_API_KEY=sk-ant-...
ovb bench --real                             # live streaming Claude calls
ovb bench --real --cassette cassettes/s1.json   # record; replay offline & keyless next time
```

## What you'll see

The task is an **interdependent** project-plan reconciliation (Scope ↔ Budget ↔
Timeline ↔ Risk). All three harnesses converge to the *identical* consistent plan;
the cost to get there is what differs:

```
  METRIC                  ORCHESTRATOR    BLACKBOARD        HYBRID
  ------------------------------------------------------------------------
  agent calls                       12             7             5   hybrid
    wasted (no-op)                   5             0             0   blackboard/hybrid
  total tokens                     898           515           373   hybrid
  cost (USD)                  0.00xx…       0.00xx…       0.00xx…   hybrid
  ------------------------------------------------------------------------
  → all topologies reached the SAME consistent plan: True
  → blackboard used 1.71× fewer calls than orchestrator
```

- The orchestrator's **5 wasted no-op calls** are the "hub tax": with no shared state,
  the only way to confirm convergence is a full re-sweep.
- The blackboard re-triggers **only** the agents a write affects.
- The hybrid does best here by *encoding the dependency structure* — it runs the tight
  Scope↔Budget cycle as a bounded blackboard, then the independent Timeline/Risk once.
  That edge is real but it costs architect insight; see [HARNESS.md](docs/HARNESS.md).

`output/report.html` is a self-contained animated report — press **play** to watch each
harness's control loop converge, meters updating live from the WORM event stream.

## Live dashboard — full visibility, side by side (`ovb serve`)

```bash
ovb serve            # opens http://127.0.0.1:8000
```

Give the **same prompt** (requested features + budget cap) to all three harnesses and
watch them run **concurrently, in real time**:

- **Compare view** — orchestrator · blackboard · hybrid side by side, or **focus** any
  one (or the hybrid) independently via the tabs.
- **Shared-memory board** — the live plan state per harness, each field flashing as it's
  written. You literally see the blackboard fill in and re-settle.
- **Agent talk** — a chat feed of what each agent "says" each turn (its narration; the
  real model's words in `--real` mode).
- **Activity · shared memory** — every activation, `✎` write, `↻` re-trigger (the reactive
  shared-memory signal), and `⏛` gate check, streamed as it happens.
- **Live meters** — calls, wasted calls, tokens, $ cost, gate status, updating per event.

It's a standard-library SSE server (no uvicorn/React/build step) streaming the same WORM
event contract the CLI and static report use — so the live view and the offline artifact
are the same data. The speed slider paces mock runs so you can watch; `--real` is paced by
real model latency. Production swaps in FastAPI + SSE + React/D3 (see [docs/PLAN.md](docs/PLAN.md)).

> ⚠️ **Honesty about the numbers.** In mock mode, tokens are *synthetic* (derived from
> real prompt lengths) so the run is reproducible offline; cost applies **real** Claude
> list prices to those tokens. Lead with **call-count** (7 vs 12) — the topology-pure
> signal — over raw tokens. Run `--real` for true tokens/latency. And note: the agents'
> numeric decisions come from deterministic rules (the LLM narrates), so this measures
> the *control-model overhead* honestly; the real-tool-use path is exercised in the
> heavier scenarios on the roadmap. Details in [docs/PLAN.md](docs/PLAN.md) §12.

## Why it's a fair comparison (and where the harness lives)

Everything that *isn't* the control model is shared exactly once; only the scheduler
differs. That's enforced in code, not by discipline:

- [`core/harness.py`](src/ovb/core/harness.py) — the `Harness` base: `invoke()` (one
  control-loop step) and `gate_passed()` (deterministic termination). **Shared.**
- [`core/state.py`](src/ovb/core/state.py) — typed `PlanState` + an ownership-checking
  reducer (every write is validated, diffed, and logged). **Shared.**
- [`core/registry.py`](src/ovb/core/registry.py), [`core/gate.py`](src/ovb/core/gate.py),
  [`core/llm.py`](src/ovb/core/llm.py), [`core/trace.py`](src/ovb/core/trace.py) — agents,
  gate, LLM clients, WORM event log. **Shared.**
- [`eval/compare.py`](src/ovb/eval/compare.py) — a `FairnessContract` that hard-fails if
  the engines weren't judged on identical terms (same roster/gate/sampling/start).

The only per-engine code is `run()` — the scheduling:
[`engines/orchestrator.py`](src/ovb/engines/orchestrator.py) ·
[`engines/blackboard.py`](src/ovb/engines/blackboard.py) ·
[`engines/hybrid.py`](src/ovb/engines/hybrid.py).

## Repo layout

```
src/ovb/
  contracts.py         canonical Usage / Event / Engine / Sequencer — the one source of truth
  config.py            RunConfig (model, temperature — fairness-critical, pinned)
  pricing.py           dated Claude list prices → real $ cost
  core/
    harness.py         the Harness base — shared control-loop primitives (invoke, gate)
    state.py           typed PlanState + ownership-enforcing reducer
    registry.py        KnowledgeSource (agent) + tools + subscription index
    gate.py            deterministic termination gate
    llm.py             MockLLM · ClaudeLLM (streaming, cache-aware) · CassetteLLM (record/replay)
    trace.py           Recorder + WORM event stream (OTel gen_ai.* aligned)
  engines/             orchestrator.py · blackboard.py · hybrid.py   (scheduling ONLY)
  domain/              task.py (scenario + gate) · agents.py (the 4 specialists)
  eval/                runner.py (build world once) · compare.py (fairness + table)
  viz/                 report.py (animated HTML) · live.py (stdlib SSE dashboard)
  cli.py               `ovb serve | bench | run | doctor`
tests/                 deterministic smoke + fairness tests (no network)
docs/                  HARNESS.md · WHEN-TO-USE.md · PLAN.md · RESEARCH.md · architecture.md
output/                generated report.html + per-engine *.jsonl event logs
```

## Documentation

- **[docs/HARNESS.md](docs/HARNESS.md)** — the harness concept, the anatomy, and the
  per-responsibility mapping across the three topologies (grounded in current sources),
  plus how the code makes it real. **Start here.**
- **[docs/WHEN-TO-USE.md](docs/WHEN-TO-USE.md)** — decision guide + checklist + hybrids.
- **[docs/PLAN.md](docs/PLAN.md)** — the full flagship implementation plan (phased, with
  the event contract, cost accounting, live dashboard, security, and a risk register).
- **[docs/RESEARCH.md](docs/RESEARCH.md)** — the cited SOTA survey.
- **[docs/architecture.md](docs/architecture.md)** — the code map.

## License

MIT — see [LICENSE](LICENSE).
