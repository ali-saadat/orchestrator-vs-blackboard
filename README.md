# Orchestrator vs Blackboard

**Same specialist agents. Same task. Two control models.** A small, dependency‑free
lab that makes the difference between the two dominant multi‑agent topologies
*measurable* — agent calls, tokens, latency, and a full audit log all come out of
instrumentation, not hand‑waving.

![Orchestrator vs Blackboard](docs/images/topologies.svg)

> The difference is not *which* agents you have — it's **how they share state and
> react**. That single choice drives token cost, auditability, determinism, and
> fit. This repo runs the exact same four agents through both models so you can
> watch the difference fall out of the numbers.

---

## The one‑paragraph version

- **Orchestrator** (hub‑and‑spoke, supervisor‑routed): a central supervisor calls
  isolated sub‑agents in a fixed order. Every call is a fresh context window
  (message‑passing). To resolve interdependencies it has to *sweep the whole roster
  again* — and pay for a final confirming sweep that changes nothing.
- **Blackboard** (shared‑state, event‑driven): all agents read/write **one** shared
  state; a write **re‑triggers only the agents that depend on it**, mid‑flight. A
  deterministic **gate** ends the run and a **control unit** caps iterations, so the
  cascade stays bounded and every write is logged (WORM) for audit.

On an *interdependent* task, the blackboard reaches the same answer with less work.
On a *linear routing* task, the orchestrator is simpler and wins. This repo lets you
see both, and [docs/WHEN-TO-USE.md](docs/WHEN-TO-USE.md) tells you which to reach for.

## Quickstart (zero dependencies)

```bash
# Mock mode is the default — deterministic, offline, no API key, stdlib only.
python demos/benchmark.py            # run BOTH, print the comparison, write output/report.html
python demos/run_orchestrator.py     # just the orchestrator trace
python demos/run_blackboard.py       # just the blackboard trace
python tests/test_smoke.py           # deterministic checks

# or via make
make bench   # == demo
make test
```

Want real model behavior and real token counts?

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python demos/benchmark.py --real
```

## What you'll see

The demo task is a **project‑plan reconciliation** with interdependent constraints
(Scope ↔ Budget ↔ Timeline ↔ Risk). Both engines converge to the identical
consistent plan; the cost to get there differs:

```
  METRIC                    ORCHESTRATOR      BLACKBOARD   advantage
  --------------------------------------------------------------------
  agent calls                        12              7   blackboard
    effective (changed)               7              7   tie
    wasted (no-op)                    5              0   blackboard
  total tokens                      908            511   blackboard
  --------------------------------------------------------------------
  → blackboard used 1.71x fewer calls and 1.78x fewer tokens
  → both reached the SAME consistent plan: True
```

The orchestrator's **5 wasted no‑op calls** are the "hub tax": with no shared state
and a fixed hand‑off order, the only way to know it's done is to re‑run everyone.
The blackboard re‑runs *only* the agents a write actually affects, and a
deterministic gate stops it the moment the plan is consistent.

`output/report.html` is a shareable, self‑contained visual: the two call traces
side by side plus the blackboard's append‑only WORM log.

> ⚠️ **Honest note on the numbers.** In mock mode, token counts are *synthetic*
> estimates derived from real prompt lengths (≈4 chars/token) so the comparison is
> reproducible and offline. Run `--real` for true token/latency numbers. The
> *ratio* — fewer calls on interdependent work — is a property of the control model,
> not of the mock.

## Why the design is fair

The whole point is an apples‑to‑apples comparison, so the parts that *aren't* the
control model are shared, exactly once:

- **`ovb/agents.py`** — the four specialists. Identical for both engines. They don't
  know or care who is scheduling them.
- **`ovb/task.py`** — the shared problem, its constraints, and the consistency
  **gate**.
- **`ovb/llm.py`** — one LLM abstraction (`MockLLM` / `ClaudeLLM`).
- **`ovb/instrumentation.py`** — one recorder + WORM log used by both.

Only two files differ, and they *are* the difference:

- **`ovb/orchestrator.py`** — fixed‑order sweeps until a sweep changes nothing.
- **`ovb/blackboard.py`** — an event loop: writes ripple to subscribed agents; a
  gate ends it; a control unit bounds it.

## Repo layout

```
ovb/                     the library (stdlib-only for mock mode)
  agents.py              the 4 specialists — SHARED by both engines
  task.py                the interdependent problem + the consistency gate
  llm.py                 MockLLM (default) and ClaudeLLM (--real)
  instrumentation.py     per-call recorder + append-only WORM log
  orchestrator.py        control model #1 — hub-and-spoke sweeps
  blackboard.py          control model #2 — shared state + reactive re-triggering
  viz.py                 console tables + self-contained HTML report
demos/                   run_orchestrator.py · run_blackboard.py · benchmark.py
tests/                   test_smoke.py (deterministic, no network)
docs/                    RESEARCH.md · WHEN-TO-USE.md · architecture.md · images/
output/                  generated report.html lands here
```

## Documentation

- **[docs/PLAN.md](docs/PLAN.md)** — the flagship implementation plan: async typed
  kernel, three engines (orchestrator/blackboard/hybrid), real streaming Anthropic
  calls with cache‑aware cost accounting, a record/replay cassette layer, one
  canonical event contract driving a live side‑by‑side dashboard, a fair 5‑scenario
  benchmark, guardrails/security, and a self‑syncing docs pipeline — phased, with a
  risk register. Built for expert agentic engineers.
- **[docs/WHEN-TO-USE.md](docs/WHEN-TO-USE.md)** — a decision guide + checklist:
  when each model wins, with worked examples.
- **[docs/architecture.md](docs/architecture.md)** — how the code maps to the
  patterns, the event‑loop mechanics, and the "bounded blackboard" idea.
- **[docs/RESEARCH.md](docs/RESEARCH.md)** — a deeper, cited survey of the SOTA and
  best practices for both control models across today's frameworks (LangGraph,
  AutoGen/Magentic‑One, OpenAI Agents SDK/Swarm, CrewAI, Anthropic's
  orchestrator‑worker, and the classical blackboard lineage).

## License

MIT — see [LICENSE](LICENSE).
