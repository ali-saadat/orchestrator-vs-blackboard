# Architecture — the code map

The repo is organized so the **control model is the only moving part**. For the
*concept* (what a harness is, why the three topologies are three harnesses), read
[HARNESS.md](HARNESS.md). This file is the map from concept to code.

## Layers

```
contracts.py ── the canonical types everyone imports (Usage, Event, Sequencer, Engine)
      │
config.py ───── RunConfig: model + temperature are pinned here so no engine samples differently
      │
core/  ──────── the domain-agnostic kernel
  harness.py     Harness base: invoke() = one control-loop step; gate_passed() = termination
  state.py       PlanState (frozen, typed) + apply_patch reducer (ownership-checked writes)
  registry.py    KnowledgeSource (agent), ToolSpec, AgentRegistry, subscription index
  gate.py        PredicateGate — deterministic "are we done?"
  llm.py         MockLLM / ClaudeLLM (streaming, cache-aware usage) / CassetteLLM (record-replay)
  trace.py       Recorder + the WORM event stream (OTel gen_ai.* aligned) + metrics
      │
engines/ ─────── the ONLY per-topology code: run() = scheduling discipline
  orchestrator.py   fixed-order sweeps to a no-op fixpoint
  blackboard.py     event loop; writes re-trigger subscribed agents; gate ends it
  hybrid.py         bounded blackboard on the coupled core, then a linear tail
      │
domain/ ──────── the swappable scenario
  task.py          initial state + the gate predicate (is_consistent)
  agents.py        the four specialists (build_registry)
      │
eval/  ───────── runner.py (build the world ONCE, run each engine) + compare.py (FairnessContract, table)
viz/   ───────── report.py: WORM events → self-contained animated HTML
cli.py ───────── ovb bench | run | doctor
```

`core/` and `engines/` never import `domain/` except through injected objects — so a
new scenario is a new `domain/` package + a `RunConfig`, nothing else.

## The shared control-loop step (why the comparison is fair)

`Harness.invoke(source, trigger)` is the single unit of agent execution, used
identically by all three engines:

```
agent_activated → llm_call → apply_patch (ownership-checked) → state_write(s) → call_finished
```

The engines differ only in *which* source they invoke *when* — that's `run()`.
Because `invoke` and the gate are shared code, the WORM logs are directly comparable
and any metric difference is attributable to scheduling alone. The `FairnessContract`
(`eval/compare.py`) asserts all engines used the same roster/gate/sampling/start and
converged to the same final state.

## The event contract (one stream, many consumers)

Every engine emits the same ordered `Event`s (`contracts.py`), keyed by a shared
monotonic `Sequencer`. `kind`s: `run_started`, `agent_activated`,
`gen_ai.client.call.started/finished`, `state_write`, `agent_retriggered`,
`gate_checked`, `run_finished`. The console trace, the animated HTML, the `*.jsonl`
logs, and (per the plan) the live SSE dashboard and OTLP export all read this one
contract. Field names track the OpenTelemetry GenAI conventions so export is a rename.

## Determinism, cost, and real mode

- **Mock mode** (default): `MockLLM` returns deterministic text with synthetic token
  counts from real prompt length. Fully reproducible; no network.
- **Real mode** (`--real`): `ClaudeLLM` streams; usage is reconciled correctly (input +
  cache from `message_start`, cumulative output from the final delta). Nondeterministic
  → the plan's harness averages N runs with bootstrap CIs.
- **Cassettes** (`--cassette`): record real calls to disk keyed by a canonical request
  hash; replay offline and deterministically. This is how real numbers stay reproducible.
- **Cost**: `pricing.py` applies dated Claude list prices to the usage vector (cache
  buckets billed at their real multipliers).

## Extending

- **New agent/constraint** — add a `KnowledgeSource` (owns + subscribes + rule) in
  `domain/agents.py`; all three engines pick it up.
- **New scenario** — new `domain/` module with `initial_state()`, a gate predicate, and
  `build_registry()`. Try a linear routing task to watch the orchestrator win.
- **New topology** — subclass `Harness`, implement `run()`, register it in
  `engines/__init__.py`.
