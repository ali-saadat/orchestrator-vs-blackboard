# Architecture — how the code maps to the two patterns

This repo is deliberately tiny so the *control model* is the only moving part.
Everything else — the agents, the task, the LLM, the instrumentation — is shared,
so a diff between the two engines is a diff between the two patterns.

## The shared substrate

| File | Role | Shared? |
| --- | --- | --- |
| `ovb/agents.py` | The four specialists (Scope, Budget, Timeline, Risk). Each *owns* fields and *subscribes* to fields. | ✅ both engines |
| `ovb/task.py` | The interdependent problem, its constraints, and `is_consistent()` — the **gate**. | ✅ both engines |
| `ovb/llm.py` | `MockLLM` (deterministic) / `ClaudeLLM` (real). Returns `Completion(text, usage)`. | ✅ both engines |
| `ovb/instrumentation.py` | `Recorder` (per‑call metrics) + WORM event log. | ✅ both engines |
| `ovb/orchestrator.py` | **Control model #1.** | ❌ the difference |
| `ovb/blackboard.py` | **Control model #2.** | ❌ the difference |

An `Agent` carries three pieces of metadata that both engines read:

```python
Agent(name, owns=[...], subscribes=[...], role="system prompt", rule=fn)
```

- `owns` — which fields it may write.
- `subscribes` — which field changes should (re)trigger it. **The orchestrator
  ignores this; the blackboard is built on it.** That asymmetry is the point.
- `rule` — the deterministic decision (used directly in mock mode; *narrated and
  validated* in real mode).

## Control model #1 — Orchestrator (`orchestrator.py`)

```
for round in 1..max_rounds:
    changed = False
    for agent in FIXED_ORDER:          # Scope → Budget → Timeline → Risk
        view  = copy(state)            # fresh, isolated context (message-passing)
        patch = agent.act(view, llm)   # sub-agent never sees the others
        apply(patch); log_calls()
        changed |= bool(patch)
    if not changed: break              # convergence = a full no-op sweep
```

Properties that fall out of this shape:

- **Isolation.** Each `act` gets a fresh `copy(state)` — sub‑agents can't see each
  other; the hub is the only integrator.
- **Fixed hand‑off order.** No mid‑task reaction. If Budget's change should wake
  Scope, that only happens on the *next* full sweep.
- **The hub tax.** Detecting "done" requires a whole extra sweep in which nothing
  changes. Those are the `wasted (no-op)` calls in the report — real tokens spent to
  confirm a fixpoint.
- **Cost ≈ roster_size × rounds.** Every agent pays every round, touched or not.

This is the right shape for **routing and linear pipelines** — see WHEN‑TO‑USE.

## Control model #2 — Blackboard (`blackboard.py`)

```
subs = index(field -> [agents subscribed to it])
queue = agents subscribed to the seed field (scope)
while queue and steps < max_steps:     # control unit caps iterations
    agent = queue.popleft()
    patch = agent.act(view=state, llm)
    for field in patch:
        log_write(field, old, new)     # WORM audit
        state[field] = new
        queue += subs[field]           # ripple to dependents only
    if is_consistent(state): break     # the GATE ends the run — not the LLM
```

Properties that fall out of *this* shape:

- **Reactive re‑triggering.** A write wakes exactly the agents that subscribe to
  that field — not the whole roster. Work is proportional to *ripples*, not
  `roster × rounds`.
- **Shared state.** One `state`; agents integrate through it instead of through a
  hub.
- **Auditability.** Every write is appended to the WORM log — you get a complete,
  ordered trail of who changed what and why.
- **Bounded & deterministic termination.** The **gate** (`is_consistent`) decides
  when to stop, and the **control unit** (`max_steps`) guarantees the cascade can't
  run away. The LLM never renders the verdict.

## The "bounded blackboard" idea

A pure blackboard's classic risk is **nondeterminism and runaway control** — writes
trigger writes with no guaranteed stop. The bounded variant keeps the reactive
shared state but wraps it in two deterministic pieces:

1. a **control unit** that schedules/caps re‑triggers (here: the queue + `max_steps`), and
2. a **gate** that decides termination with code, not a model (`is_consistent`).

That's what makes the shared‑state model safe to ship: you get mid‑flight reaction
*and* a hard, auditable stopping condition. See `docs/RESEARCH.md` for how this maps
onto BSP supersteps/reducers (Pregel‑style barrier syncs) and modern framework
primitives (e.g. LangGraph's `StateGraph` reducers and recursion limits).

## Instrumentation

`Recorder` captures, per call: engine, agent, token `Usage`, latency, whether it
changed anything, the writes, and the trigger. Aggregates (`n_calls`,
`n_effective`, `n_wasted`, `total_usage`, `total_latency_ms`, `n_writes`) drive the
comparison. Latency is real wall‑clock in `--real` mode and a reproducible synthetic
value (proportional to tokens) in mock mode, so mock results never flake.

## Extending the lab

- **Add an agent / constraint** — add an `Agent` in `agents.py` with `owns` +
  `subscribes` and a `rule`; both engines pick it up automatically.
- **Swap the task** — implement a new `initial_state()` + `is_consistent()` in a new
  task module. Try a *linear* task (classify → route → answer) to watch the
  orchestrator win instead.
- **Plug a real framework** — the engines are ~40 lines each; map `orchestrator.py`
  to a LangGraph supervisor and `blackboard.py` to a `StateGraph` with reducers to
  see the same story in production tooling.
