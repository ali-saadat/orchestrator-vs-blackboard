# OVB — Flagship Implementation Plan
## Orchestrator vs Blackboard vs Hybrid, in action, with real calls & dynamic cost/token visualization

> **Audience:** senior architects & expert agentic engineers. **Provenance:** synthesized by a 10-agent design workflow (8 expert-architect lenses → adversarial completeness critic → synthesis; ~694k tokens, 121 tool calls, incl. live verification of the Anthropic streaming-usage semantics). **Principles held throughout:** *fairness* (only the control model differs; temp=0 + N-run variance because real LLMs are nondeterministic), *real* (real Messages API calls + real data, with an offline record/replay cassette fallback), *hybrid is first-class*, and *honesty* (counter-arguments included). This plan evolves the existing `ovb` seed — it is not greenfield.

## 1. Executive summary
**ovb (Orchestrator-vs-Blackboard) becomes THE reference repo for choosing a multi-agent control model.** The seed already proves the thesis synchronously (blackboard 7 calls/511 tok vs orchestrator 12 calls/908 tok on one interdependent task). This plan hardens that proof into a flagship: a fairness-enforcing typed kernel, three engines that differ *only* in their scheduler, a five-scenario catalog with two blackboard-wins / two orchestrator-wins / one hybrid, real Anthropic streaming with correct cache-aware token accounting, a record/replay cassette layer that makes real numbers reproducible offline with no key, one canonical event contract driving CLI + live SSE UI + OTel export, a guardrails/security layer that measures injection blast-radius empirically, and a docs pipeline where no result number is ever hand-typed.

The eight design slices overlap heavily and, critically, **contradict each other on the load-bearing shared contracts** — the critic found five incompatible `Usage` schemas, six cassette-key formulas, three mutually-exclusive prompt-caching stances, two byte-incompatible event envelopes, three Engine signatures, and a redesigned blackboard scheduler that silently changes the headline number from 7 to 9 calls. This plan's central act is **resolution**: it fixes ONE canonical contract for each (Usage, cassette key, event envelope, Engine protocol, caching policy, Sequencer) in a normative `docs/CONTRACTS.md` that every module imports rather than re-declares, and it re-baselines the blackboard scheduler to preserve the seed's verified 7/511 semantics. Everything else is phased on top of that spine.

The two non-negotiables — **FAIRNESS** (only the control model differs; never credit topology for a one-line policy) and **REAL** (true tokens/cost/latency, streaming usage reconciled correctly, reproducible offline) — are enforced structurally in code (a `FairnessContract` that hard-fails CI on any divergence) and in the docs pipeline (drift is a build failure), not by reviewer discipline.

## 2. North star
**A skeptical senior engineer clones the repo, runs `uv run ovb bench` offline in under five minutes, watches the live side-by-side "cost-to-converge race," and leaves able to (a) restate the two-axis thesis, (b) name the single file that differs between engines, (c) cite a real margin *with a variance band*, (d) name a task where the blackboard *loses*, and (e) pick a topology for their own problem — and cannot find a way to break the fairness claim.**

The thesis, printed identically in README, `docs/concepts.md`, and the RESULTS header:

> The topology choice is a choice about two things: **where control lives** (a hub vs. the state itself) and **how much each agent sees of the others' work** (isolated message-passing vs. one shared board). Everything downstream — calls, tokens, latency, auditability, blast radius — falls out of those two axes.

The repo earns citation rather than skimming through three properties held together: **reproducible real numbers** (cassettes + temp=0 + N-run variance), **adversarial honesty** (orchestrator-wins scenarios, early-exit control, blast-radius, reasoning-model-substitution as first-class pages), and a **tight thesis→decision funnel**.

## 3. Phased milestones
**Phase 0 — Contract freeze + seed re-baseline (the spine).**
- *Goal:* Eliminate every cross-slice contradiction before any feature is built; prove the async blackboard still yields the seed's headline.
- *Deliverables:* `src/ovb/contracts.py` + `docs/CONTRACTS.md` (canonical Usage / cassette key / event envelope / Engine protocol / Sequencer / caching policy); src-layout + uv migration; frozen `PlanState` + `apply_patch` reducer with ownership enforcement; the ONE `Sequencer` (independent `_seq`/`_eseq`); a **verified convergence trace** for the redesigned blackboard.
- *Exit criteria:* A simulation test asserts the async blackboard produces **exactly 7 calls / 0 wasted / 511 mock tokens** (or every downstream golden is re-baselined in the same PR); `uv run ovb bench` runs offline; `grep -r "class Usage" src/` returns exactly one definition.

**Phase 1 — Provider + accounting + cassette (REAL, made reproducible).**
- *Goal:* Real streaming Anthropic calls with correct cache-aware usage, reproducible offline.
- *Deliverables:* streaming `ClaudeLLM` (cumulative-delta handling, TTFT+wall); `pricing.py`; `budget.py` (RateLimiter with rpm+tpm buckets, full-jitter backoff, `Budget`); `CassetteLLM` (record/replay, `CassetteMiss` hard-fail, MANIFEST sha256); N-run harness with **paired-difference bootstrap CIs** (stdlib only).
- *Exit criteria:* `ovb record` then `ovb replay-check` passes; a real recorded run replays byte-identical usage; **retry discards partial-stream usage** (only `message_stop` usage billed — critic must_add); rate-limiter + `asyncio.Semaphore` sized so blackboard `wall_ms < orchestrator wall_ms` is *measured under real rpm limits*, not assumed.

**Phase 2 — Three engines + scenario catalog + fairness harness.**
- *Goal:* All three engines uniform; five real-data scenarios; fairness enforced structurally.
- *Deliverables:* `orchestrator.py` (with the SHARED gate early-exit — closes the asymmetry S5's test catches), `blackboard.py`, `hybrid.py` (shared Sequencer, `gate.project()` with **documented held-constant substitution semantics** for cross-field predicates); S1–S5 scenarios with real CSV/pytest/WebSearch data + oracles; `FairnessContract.assert_comparable` + `--orch-early-exit` reporting both variants.
- *Exit criteria:* `test_fairness.py` passes (roster/gate/model/temp fingerprints identical across engines); blackboard win on S1/S2 **survives the gate-checked orchestrator**; S3/S4 show the orchestrator winning; metamorphic property: all three engines reach the identical final gate-passing state.

**Phase 3 — Instrumentation + SSE backend + live UI.**
- *Goal:* One event log drives CLI, live dashboard, and OTel export; the money-shot race renders offline.
- *Deliverables:* `EventBus` span façade + JSONL/RingBuffer sinks with **per-connection late-joiner registration** (critic must_add); FastAPI SSE app (single stack); React/D3 compare dashboard (three canvases, meter rail, WORM scrub, caveats overlay); `exporters.py`.
- *Exit criteria:* `ovb serve` renders the synchronized cost-to-converge race from cassettes with no key; a Playwright snapshot locks the money-shot frame; late-joining SSE client gets live tail (not just replay); OTLP export validates against a collector.

**Phase 4 — Guardrails, security, advisor, docs pipeline.**
- *Goal:* Safe-to-ship substrate, empirical blast-radius, and honest self-syncing docs.
- *Deliverables:* `guardrails.py` (validation, breaker, retry, governor, HITL checkpoint/resume — shared write-seam in BOTH engines); `security.py` (PoisonAgent, measured amplification factor, quarantine); `advisor.py` + `decision.yaml`; generated `RESULTS.md`/`insights.md` via `render_docs.py`; `check_docs_sync.py` + `check_anchors.py` CI gates.
- *Exit criteria:* blast-radius amplification is **computed from the WORM log and verified to exceed the orchestrator's** against the actual `scope→{Budget,Timeline,Risk}` graph (not asserted); `make check` fails on any doc/number drift or orphaned RESEARCH anchor; `ovb doctor` explains mock/cassette/real state.

## 4. MVP cut-lines (what ships in v0.1)
**Ships in v0.1 (the credible minimum):**
- `contracts.py` + `docs/CONTRACTS.md` — the canonical Usage / cassette key / event envelope / Engine protocol / Sequencer / caching policy. **This is the gate for everything; nothing else ships without it.**
- src-layout + uv; `ovb bench`, `ovb run`, `ovb replay-check`, `ovb doctor` CLI.
- Frozen `PlanState` + `apply_patch` ownership reducer; the ONE Sequencer.
- All three engines (orchestrator with shared gate early-exit, blackboard preserving 7/511, hybrid with shared Sequencer).
- **S1 (reconcile) fully wired** with real CSV + oracle; S3 (research) OR S4 (route) as the second, orchestrator-winning scenario to prove the catalog isn't rigged.
- Streaming `ClaudeLLM` + `CassetteLLM` + committed `v1` cassettes; correct cumulative-delta usage; N-run paired-diff CI harness.
- `FairnessContract` + `test_fairness.py`; golden-cassette test; hypothesis gate-convergence property.
- Generated `RESULTS.md` + `README` headline via `render_docs.py`; `check_docs_sync.py` CI gate.
- CI: ruff + mypy + pytest + replay-check, all offline.

**Deferred to v0.2+ (labeled, not silently missing):**
- The full React/D3 live dashboard and money-shot race (v0.1 ships the static, no-JS `results.html` fallback + `ovb serve` returning the JSONL/report; the animated compare-mode is v0.2).
- S2 (real pytest debug loop, vendored repo) and S5 (hybrid research-then-reconcile) — the two heaviest scenarios.
- Guardrails HITL checkpoint/resume and the cost Governor breaker (validation + ownership ship in v0.1 via the reducer; the circuit breaker, retry, and HITL are v0.2).
- Security blast-radius harness (PoisonAgent, amplification factor, quarantine) — v0.2, but the *ownership rejection* that neutralizes malformed writes is v0.1 (it lives in the reducer).
- 5m/1h cache-write split (`CacheDetail` sidecar), OTLP/Langfuse exporters, `advisor.py` + `decision.yaml` UI helper, `insights.md` waterfall, mkdocs site polish.
- Tool-use path exercised on a headline scenario (v0.1 defines `ToolSpec`/`ToolExecutor` but only S2/S3 use it in v0.2).

## 5. Success metrics
**DX / reproducibility**
- `git clone && uv sync && uv run ovb bench` completes offline, no key, in **< 5 min** on a laptop and writes `output/report.html`.
- `ovb replay-check` is green in CI; a fresh checkout at any commit reproduces the committed mock `report.json` **byte-for-byte**.
- `grep` finds exactly ONE `class Usage`, ONE cassette-key formula, ONE event envelope, ONE Engine protocol.

**Fairness (structurally enforced)**
- `FairnessContract.assert_comparable` hard-fails CI on any divergence of registry/gate/initial/model/temperature fingerprints.
- The blackboard's S1/S2 win **survives the gate-checked orchestrator** (`--orch-early-exit`); reported as both variants.
- Two scenarios show the orchestrator winning (S3/S4) — the catalog is balanced.
- Metamorphic property (hypothesis): all three engines reach the **identical** final gate-passing state for the same start.

**REAL**
- Real mode reports true `input/output/cache_creation/cache_read` tokens; streaming usage reconciled correctly (a test asserts non-double-counted cumulative deltas).
- Every real-mode margin is reported as **median + IQR + min/max over N=20 temp=0 runs**; a margin is only *claimed* when the paired-difference bootstrap CI excludes zero.
- Blackboard `wall_ms < orchestrator wall_ms` is a **measured** result under real rpm/tpm limits.

**Honesty**
- Orchestrator-wins scenario, early-exit control, blackboard's-bigger-prompts waterfall, injection blast-radius, and reasoning-model-substitution are **first-class doc pages**, not buried caveats.
- Blast-radius amplification is **computed from the WORM log** and verified to exceed the orchestrator's against the real subscription graph.
- `make check` makes any doc/number drift or orphaned RESEARCH anchor a **build failure**.

**Adoption proxy**
- A senior engineer can traverse thesis→fairness→mechanics→evidence→decision in **~8 minutes** and answer the five north-star questions.

## 6. Tech stack
| Layer | Choice | Why |
|---|---|---|
| Language / runtime | Python 3.13 (pinned via `.python-version`) | Seed is Python; async kernel needs modern asyncio; single pinned interpreter is a reproducibility floor. |
| Packaging / env | `uv` + PEP 621 `pyproject.toml`, committed `uv.lock`, src layout | `git clone && uv sync && uv run ovb bench` in <5 min; src layout catches "works from repo root, breaks when installed"; kills the seed's `PYTHONPATH` Makefile hack. |
| Base deps | **stdlib only** (Mock + cassette replay use `json`/`hashlib`) | The zero-dependency offline demo is the credibility hook; heavy deps are opt-in extras (`real`, `web`, `otel`, `viz`, `dev`). |
| Async model | `asyncio` in the kernel; commits serialized via one `Sequencer` under `asyncio.Lock`; `asyncio.Semaphore` bounds gather() width | Real parallel LLM latency becomes visible (blackboard fans out subscribers) without race order corrupting the WORM log. Semaphore reconciles concurrency with rpm limits. |
| Typed state | `pydantic` v2 (frozen `PlanState`, reducers) | Every write becomes a validated, diffable, ownership-checked event produced by engine-agnostic code. |
| Config | `pydantic-settings` (`OVB_` env prefix, nested `__`) | Single source of truth for the fairness-critical `model`/`temperature`/`max_steps` — no engine can silently use different sampling. |
| Real provider | `anthropic>=0.42`, **streaming** (`messages.stream`) | Correct cumulative-`message_delta` usage; TTFT + wall latency; cache-aware token buckets. |
| CLI | `typer` | `ovb bench/run/record/replay-check/serve/doctor`; forkable, idiomatic. |
| Web backend | **FastAPI + `sse-starlette`** (ONE stack — resolves the S3 stdlib-http.server vs S4 FastAPI split) | SSE fits append-only server→client streaming with native `Last-Event-ID` replay mapped onto monotonic `seq`; FastAPI is the idiomatic choice a senior audience expects. |
| Web frontend | Vite + React 18 + TypeScript + scoped D3 (`d3-force`/`d3-scale`/`d3-shape`/`d3-selection`) + Zustand event-reducer store | "React renders, D3 calculates" split; scrub == re-fold events 0..k through the same `applyEvent` used live. |
| Observability | OTel GenAI semantic conventions (`gen_ai.*`), optional `opentelemetry-sdk` export | Event model designed on OTel from day one → OTLP/Langfuse export is a mechanical field rename. |
| Tests | `pytest`, `pytest-asyncio`, `hypothesis` | Smoke + gate-convergence property tests + golden-cassette test + fairness assertions. |
| Docs | `mkdocs-material`, `mkdocstrings`; stdlib sentinel-templater (no Jinja) | Every result number is a generated placeholder; drift is a CI build failure. |
| CI | GitHub Actions (ruff + mypy + pytest + `ovb replay-check` + `mkdocs build --strict`) | All offline, no key; a separate manual `record.yml` refreshes cassettes. |

## 7. Consolidated repo tree
```text
ovb/                                    # repo root (evolves the seed in place)
├── pyproject.toml  uv.lock  .python-version(3.13)  .env.example
├── justfile  Makefile                  # thin wrappers over `uv run ovb …`
├── mkdocs.yml  README.md  LICENSE  CONTRIBUTING.md
├── .github/workflows/{ci.yml, record.yml}   # ci=offline gate; record=manual, uses API key
├── src/ovb/
│   ├── __init__.py                     # __version__, public re-exports
│   ├── config.py                       # NEW pydantic-settings Settings (fairness-critical params)
│   ├── cli.py                          # NEW typer app  [project.scripts] ovb=…
│   ├── contracts.py                    # NEW ★ the ONE canonical Usage, CASSETTE_KEY, event envelope,
│   │                                   #        Engine protocol, EngineResult — imported everywhere
│   ├── core/
│   │   ├── state.py                    # NEW PlanState(frozen pydantic), Patch, apply_patch reducer,
│   │   │                               #        OwnershipError; single owned-field enforcement point
│   │   ├── registry.py                 # NEW AgentRegistry, KnowledgeSource, ToolSpec, subscription index
│   │   ├── gate.py                     # NEW Gate protocol, ConsistencyGate, project() (documented semantics)
│   │   ├── sequencer.py                # NEW ★ ONE Sequencer: independent _seq/_eseq streams, injectable into sub-runs
│   │   ├── engine.py                   # NEW Engine protocol + EngineResult (the ONE signature)
│   │   └── clock.py                    # NEW Clock (real perf_counter_ns; mock virtual +=usage.total)
│   ├── llm.py                          # EVOLVED Usage(4-field canonical), MockLLM, ClaudeLLM(streaming),
│   │                                   #          CassetteLLM, get_llm/build_llm factory
│   ├── pricing.py                      # NEW $/Mtok table + cache multipliers + pricing_version + cost()
│   ├── budget.py                       # NEW RateLimiter(rpm+tpm, backoff), Budget/BudgetExceeded, CassetteMiss
│   ├── cassette.py                     # NEW record/replay store, request_key, MANIFEST.json, versioned dir
│   ├── guardrails.py                   # NEW FieldSpec/validate_write, CircuitBreaker, with_retry, Governor,
│   │                                   #        Checkpoint/Interrupt/resume (HITL)
│   ├── security.py                     # NEW Provenance(trust lattice), PoisonAgent, run_blast, gated_enqueue
│   ├── advisor.py                      # NEW loads decision.yaml → CLI + /api/advise
│   ├── instrumentation.py              # EVOLVED EventBus + span façade + Sinks; Recorder = aggregation view; report()
│   ├── exporters.py                    # NEW optional OTLP/Langfuse sinks (dependency-gated)
│   ├── report.py                       # NEW build_report/write_report → output/report.json (schema v1)
│   ├── engines/
│   │   ├── __init__.py                 # register_engine registry
│   │   ├── orchestrator.py             # EVOLVED fixed-order sweep; SHARED gate early-exit (fairness)
│   │   ├── blackboard.py               # EVOLVED FIFO-preserving scheduler (7/511 verified) + bounded gather
│   │   └── hybrid.py                   # NEW orchestrator delegating a bounded BlackboardEngine (shared Sequencer)
│   ├── scenarios/
│   │   ├── __init__.py                 # Scenario protocol + register_scenario; PRODUCES registry/gate/initial
│   │   ├── s1_reconcile.py             # seed task, constants from data/s1_estimates.csv  [BLACKBOARD]
│   │   ├── s2_debug.py                 # real pytest loop on vendored repo             [BLACKBOARD]
│   │   ├── s3_research.py              # independent fan-out (WebSearch cassettes)      [ORCHESTRATOR]
│   │   ├── s4_route.py                 # ticket routing tree                            [ORCHESTRATOR]
│   │   └── s5_hybrid.py               # research-then-reconcile                         [HYBRID]
│   ├── harness.py                      # NEW run_matrix {scenario×engine×N}, bootstrap paired-diff CIs
│   ├── viz/{console.py, report.py, assets/}   # split from seed viz.py; static results.html fallback
│   └── web/
│       ├── app.py                      # NEW FastAPI: POST /api/runs, GET SSE /events, /report, /advise, /healthz
│       ├── conductor.py                # NEW shared virtual clock for compare-mode replay
│       └── static/                     # built React SPA (D3 panels, meters, scrub, caveats)
├── web/src/                            # Vite+React+TS source (panels, store/reducer, viz wrappers)
├── cassettes/v1/                       # VERSIONED recorded interactions + MANIFEST.json (sha256/schema_version)
│   └── {s1..s5}/{orchestrator,blackboard,hybrid}.sonnet.t0.jsonl
├── data/                               # s1_estimates.csv, s1_solver.py, s2_repo/ (frozen), s4_tickets.csv
├── docs/
│   ├── CONTRACTS.md                    # NEW ★ normative: Usage, key, envelope, Engine, caching policy
│   ├── concepts.md  methodology.md  security.md  faq.md          # NEW distillation + honesty pages
│   ├── RESULTS.md  insights.md         # NEW GENERATED (never hand-edited)
│   ├── architecture.md  RESEARCH.md  WHEN-TO-USE.md              # kept (RESEARCH = cited spine)
│   └── images/                         # annotated topology SVG + generated trace/variance figures
├── tools/{render_docs.py, check_docs_sync.py, check_anchors.py}  # stdlib doc pipeline
├── tests/                             # test_smoke, test_gate_property(hypothesis), test_golden_cassette,
│                                       #   test_fairness, test_security, test_guardrails, test_events,
│                                       #   test_advisor, test_web_backend
├── demos/                             # run_matrix.py, record_cassettes.py, run_blast.py
└── output/  benchmarks/               # report.json (committed, mock) ; real_YYYYMMDD.json snapshots
```
Annotation key: **★** = the contradiction-resolving artifacts the critic's `must_add` demands; `NEW`/`EVOLVED`/`kept` = status vs seed.

## 8. Cross-cutting event & trace data contract
_The load-bearing interface: engines emit this; the CLI, the benchmark harness, and the live UI all consume it._

**These are the six cross-cutting contracts the critic flagged as mutually contradictory across slices. This plan fixes ONE of each, defined once in `src/ovb/contracts.py` + `docs/CONTRACTS.md`; every module imports, none re-declares.**

**1. Canonical `Usage` (resolves 5 incompatible definitions).** Anthropic-native 4-field set; `input_tokens` is **exclusive of cache** (Anthropic wire semantics); `prompt_tokens`/`completion_tokens` are back-compat aliases:
```python
@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0                       # UNCACHED input (Anthropic-exclusive)
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    @property
    def prompt_tokens(self)-> int: return self.input_tokens+self.cache_creation_input_tokens+self.cache_read_input_tokens
    @property
    def completion_tokens(self)-> int: return self.output_tokens
    @property
    def fair_tokens(self)-> int: return self.prompt_tokens+self.output_tokens   # multiplier-free work metric
    def __add__(self,o)->"Usage": ...            # field-wise
```
(The 5m/1h cache-write split is deferred to a later `CacheDetail` sidecar, not the core dataclass, so cassettes stay stable — see MVP cut-lines.) **OTel mapping, written once:** `gen_ai.usage.input_tokens = prompt_tokens` (INCLUSIVE, per semconv), with `gen_ai.usage.cache_read.input_tokens` / `gen_ai.usage.cache_creation.input_tokens` as sub-attributes. Every emitter uses this mapping — no slice may emit exclusive semantics under that attribute name.

**2. Canonical cassette key (resolves 6 formulas).** One formula, versioned so a format change is a detectable signal, not a cryptic miss:
```
CASSETTE_KEY = sha256("ovbkey/2|"+model|temperature|max_tokens|cache_mode|system|prompt)
```
`expect` is EXCLUDED (never on the wire); `seed` EXCLUDED (Anthropic ignores it); the `ovbkey/N` prefix and `schema_version` in MANIFEST make schema-drift → a clear "record needed" error. **Schema-evolution rule (critic must_add):** adding a `PlanState` field changes every prompt → every key. Cassettes therefore live under `cassettes/v{N}` and the manifest carries `state_schema_version`; a mismatch raises `CassetteMiss("stale schema — run `ovb record`")` rather than silently missing. Adding a scenario ships with its recorded cassette (definition of done in CONTRIBUTING).

**3. Canonical event envelope (resolves S3 string-`v`/`attributes{}`/`type` vs S4 int-`v`/`data{}`/`kind`).** Small fixed envelope + typed attribute bag; ONE shape is simultaneously WORM line, SSE frame, replay record, exporter row:
```jsonc
{ "v":"ovb.events/1", "seq":42, "run_id":"01J…", "engine":"blackboard",
  "type":"llm_call_finished", "span_id":"a1b2…", "parent_span_id":"0011…",
  "agent":"Budget", "ts_wall_ns":…, "ts_mono_ns":…, "attributes":{ … } }
```
Nine event types (`run_started/finished`, `agent_activated`, `llm_call_started/finished`, `llm_token_delta`, `state_write`, `agent_retriggered`, `gate_checked`). `seq` is uint64, per-run, **gap-free**, starts at 0, doubles as SSE `id`. **Anthropic `message_delta.usage` is CUMULATIVE** — the emitter overwrites `output_tokens`, never sums, and reads input buckets once at `message_start`. UI derives per-delta increments for the live counter.

**4. Canonical Engine protocol (resolves 3 signatures).** Async, injected deps, one result type. The `Scenario` **produces** the injected registry/gate/initial (unifying S5's Scenario with S1's injection — they are not parallel APIs):
```python
class Engine(Protocol):
    name: str
    async def run(self,*,registry:AgentRegistry, gate:Gate, initial:PlanState,
                  llm:LLMClient, config:RunConfig, rec:EventBus) -> EngineResult: ...
class Scenario(Protocol):                 # the plugin surface
    name:str
    def build(self) -> tuple[AgentRegistry, Gate, PlanState]: ...   # PRODUCES injected deps
    def oracle(self, state:PlanState) -> bool: ...
```
`EngineResult` carries `final_state, consistent, calls, writes, steps, wall_ms, total_usage`.

**5. Canonical Sequencer (resolves the seed's merged-counter corruption).** Keeps `_seq` (call) and `_eseq` (write) as **independent** monotonic streams (the seed did this correctly; the S1 redesign merged them). Commits are serialized under `asyncio.Lock`, ordered by registry index. **The hybrid injects the PARENT Sequencer into its sub-run** so nested spans share ONE gap-free per-run `seq` — satisfying the SSE client's `seq==last+1` invariant. No sub-run creates its own Sequencer.

**6. Prompt-caching fairness policy (resolves S1 "on & unbiased" vs S2 "off, favors orchestrator" vs S5 "favors blackboard").** **RESOLVED to S2's stance:** headline margin is computed on **`fair_tokens` with `cache_mode="off"`** (every call billed uncached). Caching is a **separate, explicitly-labeled benchmark axis** (`ovb bench --cache 5m` runs BOTH engines with identical breakpoints and reports per-engine hit rate). The directionality is **measured, not asserted**, and documented in `methodology.md` with a recorded number. This is the fairness-safe default; S1's "enabled by default in the core" is rejected.

## 9. Changes vs the existing `ovb` seed
**Concrete diff against the current 8-file kernel (all paths verified against the seed on disk).**

**Structural moves**
- `ovb/*.py` (flat) → `src/ovb/…` with subpackages `core/`, `engines/`, `scenarios/`, `viz/`, `web/`. Seed's 8 modules keep their semantics but move: `orchestrator.py`/`blackboard.py` → `engines/`; `task.py`+`agents.py` → `scenarios/s1_reconcile.py`.
- `Makefile` loses `export PYTHONPATH := $(CURDIR)` (the hack disappears under `uv run`); gains a `justfile`. `requirements.txt` → PEP 621 extras in `pyproject.toml` + committed `uv.lock`; `requires-python` 3.10 → **3.13** pinned.

**`ovb/llm.py` (EVOLVED, back-compat preserved)**
- `Usage(prompt_tokens, completion_tokens)` (2 fields) → canonical 4-field `Usage(input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens)` with `prompt_tokens`/`completion_tokens`/`fair_tokens` properties. **This single change resolves the five conflicting slice definitions** — every slice's `Usage` is deleted in favor of this import.
- `ClaudeLLM.complete` (non-streaming, `messages.create`, reads `msg.usage.input_tokens/output_tokens`) → **streaming** `messages.stream`: input buckets read once at `message_start`, `output_tokens` OVERWRITTEN (not summed) from cumulative `message_delta`, TTFT + wall captured. The seed's `max_tokens=256` becomes per-scenario config in the cassette key.
- `get_llm(real, model)` → `build_llm(settings)` returning MockLLM / CassetteLLM(inner=Claude) / ClaudeLLM; **cassette replay becomes the default demo path** (wraps ClaudeLLM, not MockLLM). MockLLM kept as the zero-artifact smoke fallback.

**`ovb/instrumentation.py` (EVOLVED)**
- `Recorder` with merged-behavior `record_call`/`record_write` is retained as an **aggregation view** but fed by a new `EventBus` span façade emitting the 9-type canonical envelope. `Call`/`Event` dataclasses gain `span_id`/`parent_span_id`/`provenance`.
- The seed's correct `_seq`/`_eseq` split is **preserved** in the new `core/sequencer.py` (the S1 redesign that merged them into one counter is rejected).
- `latency_for(usage, real, measured)` generalized into `core/clock.py` (real perf_counter_ns; mock virtual clock `+= usage.total`).
- New `Recorder.report()` → `report.py` serializes to `output/report.json` schema v1.

**`ovb/orchestrator.py` (EVOLVED)** — `run(llm, real, max_rounds)` (sync, fixed `ORDER`) → `async run(*, registry, gate, initial, llm, config, rec)`. **Adds the SHARED gate early-exit between agents** so the orchestrator gets the same between-step gate check the blackboard has — closing the asymmetry the critic flagged in the core. Both fixpoint and gate-checked variants reported.

**`ovb/blackboard.py` (EVOLVED, semantics-preserving)** — `run(llm, real, max_steps)` → `async run(*, …)`. Scheduler **keeps the seed's FIFO single-pop + commit-then-ripple + gate-after-each-commit** (verified 7 calls / 0 wasted / 511 tokens); `asyncio.gather` bounded by a Semaphore is applied ONLY to provably-independent frontier agents that read post-commit state — so concurrency buys wall_ms without changing the committed call set. (The S1 "gather the whole frontier against a stale snapshot" design, which the critic simulated to 9 calls, is rejected.)

**New modules** (none in seed): `contracts.py`, `config.py`, `cli.py`, `core/{state,registry,gate,sequencer,engine,clock}.py`, `pricing.py`, `budget.py`, `cassette.py`, `guardrails.py`, `security.py`, `advisor.py`, `exporters.py`, `report.py`, `harness.py`, `engines/hybrid.py`, `scenarios/{s2..s5}.py`, `web/{app,conductor}.py`, `tools/*.py`.

**Docs** — `docs/{architecture.md,RESEARCH.md,WHEN-TO-USE.md}` kept (RESEARCH is the cited spine, untouched authority). Add `CONTRACTS.md` (normative), `concepts.md`, `methodology.md`, `security.md`, `faq.md`, and GENERATED `RESULTS.md`/`insights.md`. README's currently **hardcoded** "12/908 vs 7/511" prose → sentinel-templated `{{orch.n_calls}}/{{orch.total_tokens}}` placeholders resolved from `report.json` (the highest-value sync fix — that literal is a landmine the moment `--real` numbers differ).

**Tests** — `tests/test_smoke.py` kept and extended; add `test_gate_property.py` (hypothesis), `test_golden_cassette.py`, `test_fairness.py`, `test_security.py`, `test_guardrails.py`, `test_events.py`, `test_advisor.py`, `test_web_backend.py`.

## 10. Detailed design
_Eight expert-architect slices. Each is self-contained: narrative design, concrete interfaces, key decisions, risks, and open questions._

### 10.1 OVB Core: Shared Kernel + Async Orchestrator / Blackboard / Hybrid Engine Architecture

_A redesign of the ovb kernel into an async, Pydantic-typed, fairness-enforcing core. A single AgentRegistry, StateSchema+reducers, and deterministic Gate are shared by three Engine implementations (Orchestrator, Blackboard, Hybrid) that differ ONLY in scheduling. asyncio drives real parallel LLM latency; a monotonic sequencer keeps the WORM log totally ordered; a record/replay cassette layer makes real runs reproducible offline. The fair-comparison contract is enforced structurally: engines receive the same registry, gate, schema, LLM handle, and RunConfig, and the only per-engine code is the scheduler._

#### Design goals and what changes from the seed

The seed proves the thesis synchronously with dicts and dataclasses. To become THE reference repo it needs five upgrades without breaking the fairness invariant: (1) a typed state with explicit reducers so "a write" is a first-class, auditable, conflict-checked event; (2) an `Engine` protocol so the harness/UI treat all three uniformly; (3) `asyncio` so real Anthropic calls run concurrently and latency reflects the topology (the blackboard can fan out subscribers in parallel, the orchestrator cannot cross its fixed order); (4) a `KnowledgeSource` abstraction with a real tool interface so agents can call external data, not just narrate a rule; (5) a record/replay cassette + N-run harness so nondeterministic real LLMs still yield a fair, reproducible comparison. Crucially, **the async model must not leak into the WORM log ordering or the fairness contract** — concurrency changes wall-clock latency, never the logical event sequence or the token accounting.

#### Module layout

```
ovb/
  core/
    state.py         # PlanState (Pydantic), Patch, Reducer, apply_patch
    registry.py      # AgentRegistry, KnowledgeSource, ToolSpec, subscription index
    gate.py          # Gate protocol + ConsistencyGate (wraps task.is_consistent)
    llm.py           # LLMClient protocol; MockLLM, ClaudeLLM (async, streaming usage)
    cassette.py      # record/replay layer keyed by canonical request hash
    trace.py         # Recorder, WormLog, Sequencer, Call, WriteEvent, OTel export
    config.py        # RunConfig, FairnessContract, model/temp/seed
    engine.py        # Engine protocol, EngineResult, run scaffolding
  engines/
    orchestrator.py  # supervisor sweep loop
    blackboard.py    # control unit: scheduler + gate + iteration cap
    hybrid.py        # orchestrator that invokes a bounded blackboard subroutine
  domain/
    task.py          # scenario constants + is_consistent (unchanged semantics)
    agents.py        # build_agents(): the 4 specialists as KnowledgeSources
  harness/
    runner.py        # single run + N-run variance + record/replay orchestration
    compare.py       # fairness assertions across engine results
```

`domain/` is swappable (that's the extensibility story); `core/` and `engines/` never import `domain` except through the injected registry/gate/state — so a new scenario is a new `domain/` package plus a `RunConfig`.

#### Shared typed state and reducers

`PlanState` is a frozen Pydantic model. State transitions go through **reducers**, not attribute assignment, so every mutation is (a) validated, (b) diffed, (c) emitted as a `WriteEvent` with a monotonic seq. A reducer is a pure function `(old_state, patch) -> (new_state, [WriteEvent])`. Owned-field enforcement lives here: `apply_patch` rejects a patch touching a field the agent doesn't `own`, which is the code-level guard against the prompt-injection blast-radius concern (an agent — even a subverted one — cannot write outside its owned fields; the reducer raises `OwnershipError`).

```python
class PlanState(BaseModel):
    model_config = ConfigDict(frozen=True)
    scope: int
    max_scope: int | None = None
    budget_k: int | None = None
    timeline_weeks: int | None = None
    risk: Literal["low","medium","high"] | None = None
    def fingerprint(self) -> str:  # stable hash for cassette keys & convergence
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()[:16]

class WriteEvent(BaseModel):
    seq: int; agent: str; field: str
    old: JsonValue; new: JsonValue; ts_logical: int

def apply_patch(state, patch, *, owner, owns, seq_fn) -> tuple[PlanState, list[WriteEvent]]:
    bad = set(patch) - set(owns)
    if bad: raise OwnershipError(owner, bad)
    events, changes = [], {}
    for f, v in patch.items():
        old = getattr(state, f)
        if old != v:                       # only genuine changes ripple
            changes[f] = v
            events.append(WriteEvent(seq=seq_fn(), agent=owner, field=f,
                                     old=old, new=v, ts_logical=0))
    return (state.model_copy(update=changes) if changes else state), events
```

The reducer is engine-agnostic. Both engines call the identical `apply_patch`; the WriteEvent stream is therefore produced by shared code, guaranteeing the two topologies' audit logs are comparable byte-for-byte modulo ordering.

#### Agent / KnowledgeSource abstraction and tool interface

I keep the seed's `Agent` semantics (name/owns/subscribes/role/rule) but rename to `KnowledgeSource` (the blackboard-literature term) and make `act` async and tool-aware. The `rule` remains the deterministic decision authority; the LLM narrates/validates. A `KnowledgeSource` may declare `tools: list[ToolSpec]`; in real mode these become Anthropic tool-use blocks, and the tool executor is injected (so external data — e.g., a real cost-lookup API — flows through a real tool-use round-trip, producing real tokens/latency).

```python
class ToolSpec(BaseModel):
    name: str; description: str; input_schema: dict
    handler: Callable[[dict], Awaitable[JsonValue]]  # async external data

@dataclass(frozen=True)
class KnowledgeSource:
    name: str
    owns: tuple[str, ...]
    subscribes: tuple[str, ...]
    role: str                                # system prompt persona
    rule: Callable[[PlanState], dict]        # deterministic decision authority
    tools: tuple[ToolSpec, ...] = ()

    async def act(self, view: PlanState, llm: "LLMClient",
                  tools_exec: "ToolExecutor") -> "ActResult":
        patch = self.rule(view)
        rationale = _narrate(self.name, patch)
        comp = await llm.complete(system=self.role, prompt=_prompt(self, view),
                                  expect=rationale, tools=self.tools,
                                  tools_exec=tools_exec)
        # numeric decision stays the validated rule output; comp.text is narration
        return ActResult(patch=patch, rationale=comp.text, usage=comp.usage,
                         ksource=self.name)
```

`ActResult.usage` carries the full real cost vector (below). `act` is pure w.r.t. state — it returns a patch; the engine, not the agent, applies it via `apply_patch`. This separation is what lets the same agent run under both a sequential sweep and a concurrent event loop unchanged.

#### Real usage accounting (verified against current API)

`Usage` extends the seed to the real Anthropic cost vector. Verified: streaming emits usage on `message_start` (input, cache_creation, cache_read) and a **cumulative** `message_delta.usage` (output tokens) — you take the final delta, you do not sum deltas, or you double-count. `ClaudeLLM.complete` streams and reconciles both events.

```python
class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    def cost_usd(self, price: ModelPrice) -> float: ...
    def __add__(self, o): ...   # field-wise
```

`ClaudeLLM` uses `client.messages.stream(...)`; it reads `event.message.usage` at `message_start` for input/cache fields and the last `message_delta.usage.output_tokens` for completion. Prompt caching is enabled by marking the static `role`/task-preamble with `cache_control: {"type":"ephemeral"}`; the shared preamble is identical across engines, so cache_read savings accrue equally and don't bias the comparison. Temperature is pinned to `config.temperature` (0.0 for fair runs).

#### The LLM client protocol, cassette, and reproducibility

```python
class LLMClient(Protocol):
    name: str
    async def complete(self, *, system, prompt, expect="",
                       tools=(), tools_exec=None) -> Completion: ...
```

`CassetteLLM` wraps any client. Key = `sha256(model|temperature|system|prompt|tool_defs)`. On record, it calls the real client and appends `(key, Completion)` to a JSONL cassette; on replay, it returns the stored Completion (real tokens, real text) with a synthetic-but-recorded latency. This is what makes a **real** run reproducible offline: the demo replays actual Anthropic responses without a key. `MockLLM` stays for the pure-offline deterministic default. Because the cassette is keyed on the canonical request, and both engines issue byte-identical requests for the same (agent, view), a write that recurs is a guaranteed cache/cassette hit — reinforcing fairness.

#### Sequencer: total order under concurrency

The one hard async problem: parallel `act()` coroutines must still yield a **totally ordered** WORM log. Solution: a single-owner `Sequencer` (a monotonically increasing counter owned by the engine's control loop, never by a coroutine). Coroutines run LLM calls concurrently, but **patch application is funneled through an `asyncio.Lock`-guarded `commit()`** on the control loop. Concurrency buys real latency parallelism; commit-serialization buys a deterministic event order. Determinism of *which* order is enforced by committing completed coroutines in a fixed tiebreak (registry index, then arrival seq), not in race order.

```python
class Sequencer:
    def __init__(self): self._n = 0; self._lock = asyncio.Lock()
    async def commit(self, coro_result, state, rec) -> PlanState:
        async with self._lock:            # serialize the commit, not the LLM call
            self._n += 1
            new_state, events = apply_patch(state, coro_result.patch,
                                             owner=coro_result.ksource,
                                             owns=..., seq_fn=self.next)
            for e in events: rec.record_write(e)
            rec.record_call(coro_result, seq=self._n)
            return new_state
    def next(self) -> int: self._n += 1; return self._n
```

#### The Engine protocol (uniform surface for harness/UI)

```python
class Engine(Protocol):
    name: str
    async def run(self, *, registry: AgentRegistry, gate: Gate,
                  initial: PlanState, llm: LLMClient,
                  config: RunConfig, rec: Recorder) -> EngineResult: ...

class EngineResult(BaseModel):
    engine: str
    final_state: PlanState
    consistent: bool         # gate(final_state)
    calls: list[Call]        # per-call usage/latency/trigger
    writes: list[WriteEvent] # the WORM log
    steps: int
    wall_ms: float           # real end-to-end (parallelism visible here)
    total_usage: Usage
```

Every engine receives the **same five injected dependencies** and returns the **same result type**. The UI streams `rec` events over SSE (append-only, seq-ordered) — the WORM log doubles as the live event feed, so orchestrator and blackboard render through one code path.

#### Orchestrator engine

Fixed-order supervisor sweeps. Sub-agents are isolated (fresh view each call). Within a sweep the order is fixed, so calls are **sequential** (the orchestrator's defining constraint — no mid-sweep reaction, no cross-agent parallelism). Repeats full sweeps until a no-op fixpoint or `max_rounds`.

```python
async def run(self, *, registry, gate, initial, llm, config, rec):
    state, seq = initial, Sequencer()
    for r in range(1, config.max_rounds + 1):
        changed = False
        for ks in registry.in_order(config.order):       # FIXED order
            res = await ks.act(state, llm, registry.tools_exec)
            state = await seq.commit(res, state, rec)      # sequential commit
            changed |= bool(res.patch)
        if gate(state) or not changed: break
    return EngineResult(engine="orchestrator", final_state=state, ...)
```

The orchestrator pays for ALL agents each round plus a confirming no-op sweep — that wasted work is the honest cost of fixed hand-off order, and it emerges from the loop, nothing hardcoded.

#### Blackboard engine — the Control Unit

The control unit = scheduler (subscription-driven priority queue) + gate + iteration cap. A write enqueues only SUBSCRIBED agents. The scheduler drains the **frontier** (all currently-ready agents) **concurrently** via `asyncio.gather`, commits their results in registry-index order through the Sequencer, then ripples. This is where async pays off: independent subscribers of the same write run in parallel, so real wall-clock latency drops below the orchestrator's serial sum even when token counts are close.

```python
async def run(self, *, registry, gate, initial, llm, config, rec):
    state, seq = initial, Sequencer()
    subs = registry.subscription_index()      # field -> [ksource]
    frontier = registry.subscribers_of_seed("scope")
    steps = 0
    while frontier and steps < config.max_steps:
        batch = registry.dedup(frontier)                       # one enqueue per agent
        results = await asyncio.gather(*(k.act(state, llm, registry.tools_exec)
                                         for k in batch))       # PARALLEL calls
        frontier = []
        for res in sorted(results, key=registry.index):        # deterministic commit
            state = await seq.commit(res, state, rec); steps += 1
            for f in res.patch: frontier += subs.get(f, [])     # ripple
            if gate(state): return EngineResult(..., consistent=True)
    return EngineResult(engine="blackboard", final_state=state, steps=steps, ...)
```

The gate is checked after each commit inside the batch, so the run stops the instant consistency is reached — but this early-exit policy is **shared** (the orchestrator checks the same `gate(state)`), so we never credit topology for what early-exit provides. Concurrency (gather) changes `wall_ms`, never the committed event order (sorted by registry index).

#### Hybrid engine — bounded blackboard as an orchestrator subroutine

The hybrid is a first-class engine: an orchestrator loop where one supervisor step delegates a **sub-region of the state** to a bounded blackboard subroutine, then reintegrates. Contract: the subroutine gets a `RunConfig` with a hard `max_steps` (the "bounded" in bounded-blackboard), a restricted registry (only the agents owning the delegated fields), and a **sub-gate** (a projection of the global gate onto the sub-region). It returns a `Patch` over the sub-region plus its own `Recorder` slice, which the orchestrator commits into the parent WORM log with a nested `span_id` so the trace shows the containment.

```python
async def run(self, *, registry, gate, initial, llm, config, rec):
    state, seq = initial, Sequencer()
    for r in range(1, config.max_rounds + 1):
        # supervisor handles the "trunk" fields sequentially...
        for ks in registry.in_order(config.trunk_order):
            state = await seq.commit(await ks.act(state, llm, ...), state, rec)
        # ...then delegates the interdependent cluster to a bounded blackboard
        sub_reg = registry.subset(config.delegated_agents)
        sub_gate = gate.project(config.delegated_fields)
        sub = BlackboardEngine()
        sub_res = await sub.run(registry=sub_reg, gate=sub_gate, initial=state,
                                llm=llm, config=config.bounded(max_steps=8),
                                rec=rec.child(span="hybrid.bb"))   # nested WORM
        state = seq.reintegrate(sub_res.final_state, rec)          # commit sub-writes
        if gate(state): break
    return EngineResult(engine="hybrid", final_state=state, ...)
```

`rec.child(span=...)` writes into the SAME totally-ordered WORM log with a parent seq range, so the UI can render the blackboard subroutine as a collapsible nested region inside the orchestrator timeline. Reintegration re-runs `apply_patch` so ownership is re-validated at the boundary (a delegated agent can't smuggle a write outside the delegated fields).

#### Fairness enforced at the code level

`FairnessContract.assert_comparable(results)` in `harness/compare.py` runs after every comparison and hard-fails CI if any of these differ across engines: `registry.fingerprint()` (same agents/owns/subscribes/roles), `gate.fingerprint()`, `initial.fingerprint()`, `config.model`, `config.temperature`, `config.seed`, and the tool set. Engines cannot construct their own registry/gate/state — the harness injects them; an `Engine` that tries is a type error (it has no factory). The ONLY divergent code is under `engines/`, and a lint rule forbids `engines/*` from importing `domain/` or constructing `KnowledgeSource`/`Gate`. For real (nondeterministic) runs, fairness = temp 0 + N runs + variance report + the cassette replay layer, and `compare.py` reports margins with confidence intervals rather than single numbers, plus the mock-mode exact numbers as the deterministic anchor.

#### Interfaces & contracts
###### Core protocols and signatures

```python
#### core/config.py
class RunConfig(BaseModel):
    model: str = "claude-sonnet-5"
    temperature: float = 0.0
    seed: int | None = 7
    mode: Literal["mock", "real", "replay"] = "mock"
    max_rounds: int = 10          # orchestrator / hybrid trunk
    max_steps: int = 100          # blackboard control-unit cap
    order: tuple[str, ...] = ("Scope","Budget","Timeline","Risk")
    # hybrid-only:
    trunk_order: tuple[str, ...] = ("Scope",)
    delegated_agents: tuple[str, ...] = ("Budget","Timeline","Risk")
    delegated_fields: tuple[str, ...] = ("budget_k","max_scope","timeline_weeks","risk")
    def bounded(self, *, max_steps: int) -> "RunConfig": ...

#### core/gate.py
class Gate(Protocol):
    def __call__(self, state: PlanState) -> bool: ...
    def project(self, fields: tuple[str, ...]) -> "Gate": ...   # sub-gate for hybrid
    def fingerprint(self) -> str: ...

#### core/registry.py
class AgentRegistry:
    def __init__(self, sources: list[KnowledgeSource], tools_exec: ToolExecutor): ...
    def in_order(self, order: tuple[str,...]) -> list[KnowledgeSource]: ...
    def subscription_index(self) -> dict[str, list[KnowledgeSource]]: ...
    def subscribers_of_seed(self, field: str) -> list[KnowledgeSource]: ...
    def subset(self, names: tuple[str,...]) -> "AgentRegistry": ...
    def index(self, res: "ActResult") -> int: ...   # stable tiebreak for commits
    def dedup(self, frontier: list[KnowledgeSource]) -> list[KnowledgeSource]: ...
    def fingerprint(self) -> str: ...

#### core/engine.py
class Engine(Protocol):
    name: str
    async def run(self, *, registry: AgentRegistry, gate: Gate, initial: PlanState,
                  llm: LLMClient, config: RunConfig, rec: Recorder) -> EngineResult: ...

#### core/llm.py
class Completion(BaseModel): text: str; usage: Usage; latency_ms: float
class LLMClient(Protocol):
    name: str
    async def complete(self, *, system: str, prompt: str, expect: str = "",
                       tools: tuple[ToolSpec,...] = (),
                       tools_exec: "ToolExecutor | None" = None) -> Completion: ...

#### harness/runner.py
async def run_once(engine: Engine, *, registry, gate, config, llm) -> EngineResult: ...
async def run_n(engine: Engine, n: int, **kw) -> "VarianceReport": ...
#### harness/compare.py
class FairnessContract:
    @staticmethod
    def assert_comparable(results: list[EngineResult], *, registry, gate,
                          initial, config) -> None: ...  # raises on any divergence
```

###### Cassette record (JSONL, one line per LLM call)
```json
{"key":"sha256:...","model":"claude-sonnet-5","temperature":0.0,
 "system":"You are the Budget owner...","prompt":"Current plan state:...",
 "completion":{"text":"Budget: adjusting budget_k->90, max_scope->6.",
   "usage":{"input_tokens":312,"output_tokens":24,
            "cache_creation_input_tokens":0,"cache_read_input_tokens":288}},
 "latency_ms":842.0}
```

###### WORM event stream (SSE frame + OTel mapping)
```json
{"seq":14,"kind":"call","engine":"blackboard","agent":"Risk",
 "trigger":"timeline_weeks changed","usage":{...},"latency_ms":611.0,
 "writes":{"risk":"medium"},"span_id":"…","parent_span":"…"}
```
OTel GenAI export per call: `gen_ai.operation.name="chat"`,
`gen_ai.request.model`, `gen_ai.request.temperature`,
`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
`gen_ai.agent.name=<ksource>`; blackboard batches are sibling spans under a
`step` span, hybrid sub-runs nest under a `hybrid.bb` span so the trace tree
mirrors the containment.

###### ToolExecutor contract (real external data path)
```python
class ToolExecutor:
    async def dispatch(self, name: str, args: dict) -> JsonValue: ...
    # real mode: agent emits tool_use -> executor runs handler -> tool_result ->
    # model continues; every hop's tokens land in the same Usage vector.
```

#### Key decisions
- **State is a frozen Pydantic model mutated only through a shared apply_patch reducer that enforces field ownership.** — Makes every write a validated, diffable, auditable event produced by ENGINE-AGNOSTIC code, so both topologies' WORM logs are comparable by construction; ownership checks give a concrete code-level answer to the prompt-injection blast-radius concern (a subverted agent still cannot write fields it doesn't own). _(alt: Keep raw dicts (seed) — no validation, no ownership guard; or per-engine mutation — would let topology bias the audit log.)_
- **asyncio concurrency for LLM calls, but patch commits are serialized through a single Sequencer under an asyncio.Lock, ordered by registry index.** — Real parallel latency becomes visible (blackboard fans out subscribers concurrently; orchestrator's fixed order stays serial) WITHOUT letting race order corrupt the totally-ordered WORM log. Concurrency affects wall_ms only, never the logical event sequence or token accounting. _(alt: Fully sequential (seed) hides the topology's real latency advantage; or lock-free commit — nondeterministic event order breaks reproducibility and the fair comparison.)_
- **A single Engine protocol with five injected dependencies (registry, gate, initial state, llm, config) and one EngineResult type; engines live under engines/ and may not import domain/ or build a KnowledgeSource/Gate.** — Structurally guarantees the only divergent code is the scheduler. The harness/UI treat all three engines uniformly and a FairnessContract can hard-fail CI on any divergence of registry/gate/state/model/temp fingerprints. _(alt: Free-form run() functions (seed) — nothing stops an engine from quietly using a different order-policy or gate and stealing credit for the topology.)_
- **Hybrid is a real engine: an orchestrator that delegates an interdependent sub-region to a BlackboardEngine instance with a bounded max_steps, a subset registry, and a projected sub-gate, then reintegrates via apply_patch into the same nested WORM log.** — Makes bounded-blackboard first-class and honest — the subroutine reuses the exact blackboard engine (not a copy), boundedness is a config cap, and reintegration re-validates ownership at the boundary. _(alt: Hardcode a special-case hybrid loop — would duplicate scheduler logic and let the two blackboards drift, breaking fairness.)_
- **Three LLM tiers behind one protocol: MockLLM (deterministic offline default), ClaudeLLM (real streaming, full cache-aware Usage vector), CassetteLLM (record/replay of real responses).** — Satisfies REAL (true tokens/cost/latency, streaming usage reconciled correctly since message_delta is cumulative) and reproducibility (replay real responses offline without a key). Cassette keys on the canonical request so recurring writes are guaranteed hits, reinforcing fairness. _(alt: Only mock+real (seed) — real runs are non-reproducible and can't be demoed offline, undermining the fair N-run comparison.)_
- **Keep the deterministic rule as the decision authority; the LLM only narrates/validates, and numeric patches come from the rule.** — Preserves the seed's core fairness trick — real tokens/latency are genuine but the plan can't go off the rails, so the two topologies stay numerically comparable even with a nondeterministic model. _(alt: Let the model decide values — introduces nondeterminism that would swamp the topology signal and make honest margins impossible.)_

#### Risks
- **asyncio.gather in the blackboard could make the 'parallel' latency advantage look artificially large if the mock/replay latency is synthetic and uniform.** → In mock/replay, derive per-call latency from real recorded values (cassette) or a token-proportional model; report wall_ms separately from the sum-of-call latency so readers see both the serial cost and the parallel wall-clock, and never conflate them.
- **Cumulative message_delta usage in streaming is easy to mis-sum, double-counting cache tokens and corrupting the cost comparison.** → ClaudeLLM reads input/cache fields from message_start and takes the FINAL message_delta.usage.output_tokens (never sums deltas); a unit test asserts reconstructed Usage equals the non-streamed usage for the same request.
- **Prompt caching could bias the comparison if one engine benefits from cache_read more than the other (e.g., blackboard re-invokes the same agent/view more often).** → Report cache_creation and cache_read tokens as separate columns and also report an uncached-equivalent cost; the shared static preamble is identical across engines so baseline cache behavior is symmetric, and compare.py surfaces any asymmetry.
- **Serializing commits under a lock could reintroduce a hidden sequential bottleneck that erases the async benefit, or conversely a bug could let two coroutines commit against a stale state.** → The lock guards only commit() (microseconds), not the LLM call; commit re-reads current state and re-applies apply_patch, so a coroutine computed against a stale view still produces a genuine diff against live state (idempotent no-op if superseded). Property test: N concurrent commits yield the same final state and seq order as sequential replay.
- **Hybrid's nested WORM log could break total ordering if the sub-engine owns its own Sequencer.** → The sub-engine receives the PARENT Sequencer via rec.child(); it never allocates its own counter, so sub-writes get parent-monotonic seqs and the containment is expressed only by span_id/parent_span, not by a separate numbering.
- **FairnessContract fingerprints could pass while a subtle divergence (e.g., differing max_tokens or system-prompt whitespace) still biases tokens.** → Fingerprint the FULL canonical request template (system+prompt skeleton+tool defs+max_tokens+temperature), not just semantic fields; the cassette key reuses the same canonicalization, so any drift changes the key and is caught by a replay miss in CI.

#### Open questions
- Should the blackboard commit the WHOLE ready frontier before checking the gate, or check the gate after each in-batch commit? Checking per-commit gives the earliest honest exit but makes the parallel batch partially wasted; committing the whole batch is simpler but may over-run by up to |batch|-1 calls. Current design checks per-commit inside the sorted batch — needs a decision doc since it slightly changes the wasted-call count.
- Does the tool-use round-trip (external data) belong inside act() as a single logical call, or as separate WORM events per hop? Separate events are more auditable but inflate the call count asymmetrically if only some agents use tools — may need a 'sub-call' event kind that doesn't count toward the topology's step budget.
- For real N-run variance, what statistic is the headline margin — median call-count (integer, stable) or mean token cost with CI? Mixing them across the mock anchor and real runs needs one canonical reporting rule in compare.py.
- Should hybrid delegation be static (config-declared delegated_agents) or discovered by the supervisor at runtime (dynamic sub-region selection)? Dynamic is more realistic but reintroduces a policy the orchestrator lacks, threatening fairness — likely keep static for the flagship comparison and show dynamic only in an appendix engine.
- How aggressively should prompt caching be applied to the per-agent role vs. the shared task preamble? Caching the role blocks too gives bigger savings but could differentially favor whichever engine re-invokes a given agent most — need an experiment to confirm symmetry before enabling by default.

### 10.2 Provider Layer + Token/Cost/Latency Accounting for the OVB Reference Repo

_A drop-in upgrade to ovb/llm.py that preserves the existing complete(system,prompt,expect)->Completion seam but replaces the two-field Usage with a six-field billing record (input, output, cache_write_5m, cache_write_1h, cache_read, plus derived billed/wire totals). Adds a streaming Anthropic provider with correct cumulative-delta usage parsing, a record/replay cassette layer for offline determinism, a $/Mtok pricing model with cache multipliers, a token-bucket RateLimiter with 429/Retry-After backoff and a hard Budget guard, and an N-run temp=0 harness reporting mean+stdev+CI. The central fairness policy: engines are compared on billed tokens with prompt caching DISABLED by default, because caching rewards prompt-prefix stability which is a topology artifact, not control-model quality, and would silently credit the orchestrator's fixed-order sweeps. Caching is a separate, explicitly-labeled benchmark axis, never folded into the headline orchestrator-vs-blackboard margin._

#### Scope and the one hard constraint

My slice sits behind the existing seam: `llm.complete(system, prompt, expect="") -> Completion(text, usage)`. Both engines call this identically via `agent.act(view, llm)` in `agents.py`, so fairness holds automatically as long as I do not change that signature. What I change is the *richness* of `usage`, the *reality* of the numbers, and the reproducibility machinery. Everything is additive to `ovb/llm.py` plus three new modules: `ovb/pricing.py`, `ovb/cassette.py`, `ovb/budget.py`.

#### The Usage record: six fields, not two

The current `Usage(prompt_tokens, completion_tokens)` cannot express caching or cost. I replace it with a field-compatible superset. I keep `prompt_tokens`/`completion_tokens` as computed aliases so `instrumentation.py` (`total_usage`, `latency_for`) keeps working unmodified:

```python
@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0          # UNCACHED input only (Anthropic semantics)
    output_tokens: int = 0
    cache_write_5m_tokens: int = 0 # ephemeral_5m_input_tokens
    cache_write_1h_tokens: int = 0 # ephemeral_1h_input_tokens
    cache_read_tokens: int = 0
    @property
    def prompt_tokens(self) -> int:      # back-compat alias
        return (self.input_tokens + self.cache_write_5m_tokens
                + self.cache_write_1h_tokens + self.cache_read_tokens)
    @property
    def completion_tokens(self) -> int:
        return self.output_tokens
    @property
    def total(self) -> int:
        return self.prompt_tokens + self.output_tokens
    def __add__(self, o): ...  # field-wise sum, unchanged contract
```

The single most important, non-obvious fact that drives this whole design: in the Anthropic Messages API, `usage.input_tokens` is **exclusive** of cached tokens — it counts only the *uncached* portion of the prompt. `cache_read_input_tokens` and `cache_creation_input_tokens` are reported *separately alongside* it. This is the opposite of the OpenTelemetry GenAI convention, where `gen_ai.usage.input_tokens` SHOULD be inclusive of cache tokens. So my `prompt_tokens` alias reconstructs the wire total (what a naive reader expects) by summing all four input buckets, while the raw `input_tokens` field preserves Anthropic's billed-uncached semantics. When I emit OTel spans I map `gen_ai.usage.input_tokens = usage.prompt_tokens` (inclusive) per the semconv, and carry `gen_ai.usage.cache_read.input_tokens` / `gen_ai.usage.cache_creation.input_tokens` as the sub-attributes. Getting this backwards silently under- or double-counts; it is the #1 accounting bug in the ecosystem (langchain #10249, cline #4346).

#### The streaming provider and the cumulative-delta trap

`ClaudeLLM.complete` becomes a streaming call. Streaming matters here for real latency: I capture **time-to-first-token (TTFT)** and **total wall time** separately, because for a fan-out topology the interesting cost is not just tokens but how latency composes across serialized vs parallelizable calls. The parsing rule that must be exactly right:

- `message_start.usage` carries the full input accounting: `input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, and the nested `cache_creation.{ephemeral_5m_input_tokens, ephemeral_1h_input_tokens}`. Output tokens here are only the priming count (usually 1–4).
- `message_delta.usage.output_tokens` is **cumulative, not incremental**. You take the *last* value seen, you do not sum deltas. (Summing is the second classic bug.) `message_delta` may also restate `input_tokens`; I ignore the delta's input restatement and trust `message_start` for input buckets to avoid the double-count class of bugs.

So the provider reads input buckets once at `message_start`, then overwrites `output_tokens` on every `message_delta`, and finalizes at `message_stop`. Concretely:

```python
def complete(self, system, prompt, expect="", *, cache_mode="off"):
    self._rate.acquire()  # token-bucket, may block
    system_blocks = self._build_system(system, cache_mode)  # cache_control on prefix
    t0 = time.perf_counter(); ttft = None
    inp = {}; out = 0; text = []
    with self._client.messages.stream(
            model=self._model, max_tokens=256, temperature=0,
            system=system_blocks,
            messages=[{"role": "user", "content": prompt}]) as s:
        for ev in s:
            if ev.type == "message_start":
                inp = _read_input_buckets(ev.message.usage)
            elif ev.type == "content_block_delta" and ev.delta.type == "text_delta":
                if ttft is None: ttft = (time.perf_counter()-t0)*1000
                text.append(ev.delta.text)
            elif ev.type == "message_delta":
                out = ev.usage.output_tokens  # cumulative -> overwrite
    wall = (time.perf_counter()-t0)*1000
    usage = Usage(**inp, output_tokens=out)
    rec = CallRecord(... usage, ttft_ms=ttft, wall_ms=wall ...)
    self._cassette.append(rec)  # record mode
    self._budget.charge(price(usage, self._model, self._pricing))
    return Completion(text="".join(text), usage=usage)
```

`temperature=0` is hard-wired in the provider, not left to callers — it is a fairness invariant, not a tuning knob. Even at temp=0 Claude is not bit-deterministic (MoE routing, batching), which is exactly why the cassette and N-run harness exist.

#### Prompt caching vs fair comparison — the policy that matters most

Caching is a landmine for a *fair* topology comparison and I take a firm, opinionated stance. Prompt caching bills cache *writes* at 1.25x (5m TTL) or 2.0x (1h TTL) of base input, and cache *reads* at 0.1x. A cache hit therefore depends entirely on **prompt-prefix stability across successive calls** — whether call N+1 reuses call N's exact system+prefix. That stability is a property of *how the topology sequences and templates its prompts*, not of the control model's decision quality. The orchestrator's fixed-order sweeps re-issue near-identical prompts and would rack up cheap cache reads; the blackboard's reactive, data-dependent ordering has a colder prefix. Turning caching on would credit the orchestrator for token *plumbing* and directly violate NON-NEGOTIABLE #1 ("never credit the topology for what a one-line policy provides").

Policy, enforced in code:
1. **`cache_mode="off"` is the default and the only mode used for the headline orchestrator-vs-blackboard margin.** No `cache_control` blocks are emitted; every call is billed at full uncached input. This is the apples-to-apples number.
2. Caching is a **separate benchmark axis**: `benchmark.py --cache 5m` runs *both* engines with identical caching policy (same cache breakpoints on the same shared system prefix) and reports a distinct "cost with caching" table plus the **effective cache hit rate per engine**. This is honest and interesting — it *quantifies* the plumbing advantage rather than hiding it — but it is never the headline.
3. The report shows two cost columns: **billed_cost** (what you pay, cache-aware) and **effective_uncached_cost** (what you would pay with no cache). The fairness comparison uses `effective_uncached_cost` so an accidental cache hit can never move the margin.

I compute a scalar **`billed_input_tokens`** = `input_tokens*1.0 + cache_write_5m*1.25 + cache_write_1h*2.0 + cache_read*0.1`, and the fairness metric `fair_tokens` = `input_tokens + cache_read + cache_write_* ` (raw wire tokens, multiplier-free) so the topology comparison is on *work done*, not *dollars*, immune to pricing changes.

#### Pricing model

`ovb/pricing.py` is a small, dated, source-cited table — not hardcoded magic numbers scattered in code. Per-model `$/Mtok` for input and output, with cache multipliers as model-independent constants (1.25 / 2.0 / 0.1), plus a `pricing_version` date string that lands in every `CallRecord` so an old cassette replays with the prices it was captured under (or `--reprice` to recompute against current). `cost(usage, model)` returns a `Cost(input_usd, output_usd, cache_write_usd, cache_read_usd, total_usd)`. Because pricing lives beside the cassette version, cost is fully reproducible offline.

#### Cassette record/replay

`ovb/cassette.py` gives deterministic, key-free, offline runs while still exercising the *identical* code path. A cassette is a JSONL file, one `CallRecord` per line, keyed by a **request digest** = `sha256(model + temperature + system + prompt + max_tokens + cache_mode)`. Note `expect` (the agent's narration hint) is deliberately **excluded** from the digest — it never goes on the wire — so the key reflects only what the API actually sees.

- **Record mode** (`--real --record run.jsonl`): the real provider runs, and every `(digest -> CallRecord)` is appended WORM-style (mirrors the existing WORM ethos in `instrumentation.py`).
- **Replay mode** (`--replay run.jsonl`, the CI default): `ReplayLLM.complete` hashes the request, looks up the record, returns the recorded `text` + `Usage` + latencies with **zero network and no API key**. A missing digest is a hard error (`CassetteMiss`), never a silent live call — that would break offline determinism.
- Because both engines are deterministic given fixed LLM outputs, a single cassette recorded once makes the *entire* benchmark bit-reproducible, including latency (replayed from recorded `wall_ms`, not re-clocked). This is how the repo ships honest real-API numbers that anyone can reproduce without a key.

Collision handling: if the same digest recurs (e.g. orchestrator re-issues an identical prompt), replay serves the *first-recorded* response for that digest — correct, because a temp=0 identical request is defined to be equivalent. An `--strict-order` mode instead replays in recorded sequence and asserts the digest matches, catching accidental prompt drift between record and replay.

#### RateLimiter, backoff, Budget

`ovb/budget.py`:
- **`RateLimiter`**: a token-bucket over *requests/min* and a second bucket over *input-tokens/min* (Anthropic enforces both). `acquire(est_tokens)` blocks until both buckets permit. On a real `429`, it honors `Retry-After` if present, else full-jitter exponential backoff (`min(cap, base*2**n)` then uniform[0, that]); on `529 overloaded` same policy. `529` and `429` are retried; `400`-class are raised immediately (they will never succeed).
- **`Budget`**: a hard USD ceiling and a call ceiling. `charge(cost)` accumulates; exceeding the ceiling raises `BudgetExceeded`, which the demos catch and report as a partial run rather than crashing. This is what makes it safe to point the flagship at the real API in a workshop. The blackboard's `max_steps` and orchestrator fixpoint already bound *iterations*; Budget bounds *dollars* orthogonally.

#### N-run averaging, variance, and the reported metric

Real LLMs are nondeterministic even at temp=0, so a single real run is not a measurement. `benchmark.py` gains `--runs N` (default 5 for `--real`, 1 for replay since replay is deterministic). For each engine it collects per-run vectors of `{fair_tokens, billed_cost_usd, wall_ms, n_calls, n_effective}` and reports **mean, sample stdev, and a 95% CI half-width** (`t_{0.975,N-1} * s/sqrt(N)`; I ship a tiny t-table to stay stdlib-only per the repo's zero-dependency mock ethos). The headline claim is stated as an interval: e.g. "blackboard uses 7.0±0 calls, orchestrator 12.0±0; fair-token margin 44% [95% CI 41–47%]." `n_calls` is usually variance-free because the deterministic gate in `task.py` fixes the control flow; the *token* counts carry the LLM variance. The report explicitly separates **structural metrics** (calls, writes, effective/wasted — governed by control logic, ~zero variance) from **LLM metrics** (tokens, cost, latency — carry API variance). This is the honest way to show the margin is real and not a lucky sample.

#### The reasoning-model caveat (cost framing)

The report's cost section carries a standing caveat: a single call to a reasoning model with a large thinking budget can substitute for a multi-agent fan-out, and its **thinking tokens are billed as output tokens** — so a "1 agent" reasoning run can cost *more* than a "4 agent" non-reasoning blackboard while looking simpler. Any cost comparison therefore fixes the model tier across all engines (already an invariant) and, when a reasoning model is used, reports thinking-token output separately so the fan-out-vs-reasoning tradeoff is legible rather than hidden inside `output_tokens`.

#### Wiring: minimal, fairness-preserving

`get_llm(real, model, *, replay=None, record=None, cache_mode="off", pricing=None)` is the single factory the demos already call. It returns `MockLLM` / `ClaudeLLM` / `ReplayLLM` — all three honor the identical `complete(...)` signature, so `orchestrator.py` and `blackboard.py` need **zero changes**. That is the proof the accounting layer is topology-neutral: the engines cannot even tell which provider they hold.

#### Interfaces & contracts
##### Files
- `ovb/llm.py` — extend `Usage`; add streaming `ClaudeLLM`, `ReplayLLM`; widen `get_llm`.
- `ovb/pricing.py` — pricing table + `cost()`.
- `ovb/cassette.py` — `CallRecord`, `Cassette`, digest.
- `ovb/budget.py` — `RateLimiter`, `Budget`, backoff.

##### Usage (ovb/llm.py) — field-compatible superset
```python
@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0          # UNCACHED input (Anthropic semantics)
    output_tokens: int = 0
    cache_write_5m_tokens: int = 0
    cache_write_1h_tokens: int = 0
    cache_read_tokens: int = 0
    @property
    def prompt_tokens(self) -> int: ...   # sum of all 4 input buckets (wire total; OTel-inclusive)
    @property
    def completion_tokens(self) -> int: return self.output_tokens
    @property
    def total(self) -> int: ...
    @property
    def fair_tokens(self) -> int:         # multiplier-free work metric
        return self.prompt_tokens + self.output_tokens
    def __add__(self, o: "Usage") -> "Usage": ...  # field-wise
```

##### Provider interface (structural protocol — no ABC needed)
```python
class LLMProvider(Protocol):
    name: str
    def complete(self, system: str, prompt: str, expect: str = "",
                 *, cache_mode: Literal["off","5m","1h"] = "off") -> "Completion": ...
```
`Completion(text: str, usage: Usage)` unchanged. `cache_mode` is keyword-only with default `"off"`; agents never pass it, so `agents.py` is untouched. `MockLLM.complete` ignores `cache_mode` and returns synthetic per-bucket counts (all input in `input_tokens`).

##### CallRecord schema (ovb/cassette.py) — one JSONL line
```python
@dataclass(frozen=True)
class CallRecord:
    digest: str            # sha256(model|temp|system|prompt|max_tokens|cache_mode)
    model: str
    temperature: float     # always 0.0
    cache_mode: str        # "off" | "5m" | "1h"
    system: str
    prompt: str
    max_tokens: int
    text: str              # model output (replayed verbatim)
    usage: dict            # Usage.__dict__ (5 fields)
    ttft_ms: float | None  # time-to-first-token
    wall_ms: float         # total wall time (replayed as latency)
    pricing_version: str   # e.g. "2026-06-01"
    stop_reason: str
    ts: str                # ISO8601 capture time (audit only, not in digest)
```
JSONL example:
```json
{"digest":"a1b2...","model":"claude-sonnet-5","temperature":0.0,"cache_mode":"off","system":"You are the Budget owner...","prompt":"Current plan state: {...}","max_tokens":256,"text":"Budget: adjusting budget_k->120...","usage":{"input_tokens":142,"output_tokens":38,"cache_write_5m_tokens":0,"cache_write_1h_tokens":0,"cache_read_tokens":0},"ttft_ms":410.2,"wall_ms":980.5,"pricing_version":"2026-06-01","stop_reason":"end_turn","ts":"2026-06-30T12:00:01Z"}
```

##### Anthropic streaming event -> Usage mapping (the exact rule)
```
message_start.usage      -> input_tokens, cache_read_input_tokens,
                            cache_creation.ephemeral_5m_input_tokens,
                            cache_creation.ephemeral_1h_input_tokens
message_delta.usage      -> output_tokens is CUMULATIVE: OVERWRITE, do not sum;
                            ignore any input restatement here (trust message_start)
message_stop             -> finalize
```
`input_tokens` from the API is uncached-only; do NOT add cache tokens into it. `_read_input_buckets(u)` returns `{input_tokens:u.input_tokens, cache_read_tokens:u.cache_read_input_tokens, cache_write_5m_tokens:getattr(u.cache_creation,'ephemeral_5m_input_tokens',0), cache_write_1h_tokens:...}`.

##### Pricing (ovb/pricing.py)
```python
PRICING_VERSION = "2026-06-01"
CACHE_WRITE_5M_MULT = 1.25
CACHE_WRITE_1H_MULT = 2.00
CACHE_READ_MULT     = 0.10
PRICES = {  # $/Mtok, fill from current Anthropic pricing at capture time
    "claude-sonnet-5": {"in": 3.00, "out": 15.00},
}
@dataclass(frozen=True)
class Cost:
    input_usd: float; output_usd: float
    cache_write_usd: float; cache_read_usd: float; total_usd: float
def cost(u: Usage, model: str) -> Cost: ...
def billed_input_tokens(u: Usage) -> float:  # cache-multiplier-weighted, for billed_cost
    ...
```

##### Budget / RateLimiter (ovb/budget.py)
```python
class RateLimiter:
    def __init__(self, rpm: int, tpm: int): ...
    def acquire(self, est_input_tokens: int) -> None: ...   # blocks on both buckets
    def on_429(self, retry_after: float | None, attempt: int) -> float: ...  # sleep secs, full-jitter
class Budget:
    def __init__(self, usd_cap: float, call_cap: int): ...
    def charge(self, c: Cost) -> None:  # raises BudgetExceeded past ceiling
    spent_usd: float; n_calls: int
class BudgetExceeded(RuntimeError): ...
class CassetteMiss(KeyError): ...   # replay digest not found -> hard fail, never live-call
```
Retry policy: retry on `429`,`529`; honor `Retry-After` else `sleep = uniform(0, min(60, 2**attempt))`; max 6 attempts; `4xx` (non-429) raised immediately.

##### Factory + CLI surface (no engine changes)
```python
def get_llm(real=False, model="claude-sonnet-5", *, replay=None, record=None,
            cache_mode="off", pricing=PRICING_VERSION,
            rpm=50, tpm=40000, usd_cap=5.0, call_cap=500) -> LLMProvider: ...
```
demos/benchmark.py new flags: `--runs N`, `--replay FILE`, `--record FILE`, `--cache {off,5m,1h}`, `--usd-cap X`. Reported per engine: `n_calls`, `n_effective`, `n_wasted` (structural, ~0 variance) and `fair_tokens`, `billed_cost_usd`, `effective_uncached_cost_usd`, `wall_ms`, `ttft_ms` (mean ± stdev ± 95% CI over `--runs`). Headline margin computed on `fair_tokens` / `effective_uncached_cost_usd` with `cache_mode=off`.

#### Key decisions
- **Compare engines with prompt caching OFF by default; caching is a separate, explicitly-labeled benchmark axis.** — Cache hits depend on prompt-prefix stability across calls, which is a function of how a topology sequences/templates prompts, not of control-model quality. Enabling caching would credit the orchestrator's repetitive fixed-order sweeps with cheap cache reads and violate the fairness principle. _(alt: Enable caching everywhere and compare billed cost (rejected: rewards plumbing, hides the real margin, non-reproducible across pricing changes).)_
- **Report the headline margin in raw fair_tokens (multiplier-free wire tokens), not dollars.** — Tokens measure work done and are immune to pricing table changes and cache multipliers; dollars are a derived, volatile view kept in a separate column. _(alt: Headline in USD (rejected: couples the claim to a dated price table).)_
- **Keep the exact complete(system,prompt,expect) seam and keyword-only cache_mode; add all richness inside Usage and new modules.** — orchestrator.py and blackboard.py need zero changes, which is itself the proof the accounting layer is topology-neutral — the engines cannot tell which provider they hold. _(alt: New provider method signature (rejected: forces engine edits and risks asymmetric call sites that break fairness).)_
- **Anthropic input_tokens is treated as uncached-only; prompt_tokens alias reconstructs the inclusive total.** — The API reports input_tokens EXCLUSIVE of cache tokens; conflating them is the ecosystem's #1 accounting bug. OTel expects an inclusive value, so the alias bridges the two conventions explicitly. _(alt: Trust input_tokens as the full prompt count (rejected: undercounts by the cached amount).)_
- **Streaming: read input buckets once at message_start; overwrite (never sum) the cumulative output_tokens from message_delta.** — message_delta.usage is cumulative; summing double-counts, and re-reading input from deltas double-counts cache tokens (langchain #10249, cline #4346). _(alt: Sum deltas (rejected: inflates output); non-streaming (rejected: loses TTFT for the latency-composition story).)_
- **Cassette digest excludes the agent's `expect` narration hint.** — expect never goes on the wire; keying on the actual request (model,temp,system,prompt,max_tokens,cache_mode) makes replay match what the API truly saw and keeps identical wire-requests deduplicated. _(alt: Include expect in the key (rejected: spurious cache misses when only narration hints differ).)_
- **N-run harness reports structural metrics and LLM metrics separately, each with mean+stdev+95% CI.** — Control-flow metrics (calls/writes) are ~variance-free because the deterministic gate fixes them; token/cost/latency carry genuine LLM nondeterminism. Separating them shows the margin is structural, not a lucky sample. _(alt: Single blended average (rejected: hides that the call-count win is deterministic while token counts vary).)_
- **Replay is the CI default; a missing digest is a hard CassetteMiss, never a silent live call.** — Guarantees offline, key-free, bit-reproducible benchmarks including latency (replayed from recorded wall_ms), and prevents accidental spend or nondeterminism creeping into CI. _(alt: Fall through to live API on miss (rejected: breaks reproducibility and can incur cost/require keys in CI).)_

#### Risks
- **Prompt caching silently distorts the fairness comparison by crediting the orchestrator's repetitive prompts with cheap cache reads.** → cache_mode='off' is the enforced default for the headline margin; caching runs are a separate labeled axis; the fairness metric uses effective_uncached_cost and multiplier-free fair_tokens so an accidental hit cannot move the number.
- **Misreading Anthropic streaming usage (cumulative deltas, uncached-only input_tokens) yields silently wrong token/cost totals.** → Provider reads input buckets once at message_start, overwrites output_tokens from message_delta, ignores delta input restatements; a unit test asserts cache_read+cache_write+input reconstructs the wire total and that summing deltas is never done.
- **LLM nondeterminism at temp=0 makes a single real run non-reproducible, undermining the 'real numbers' claim.** → temp=0 hard-wired in the provider; N-run harness with stdev/CI; cassette record/replay makes the shipped benchmark bit-reproducible without a key.
- **Live real-API runs in a workshop overspend or hit rate limits and crash the demo.** → Hard USD/call Budget ceiling raising catchable BudgetExceeded (partial run reported), token-bucket RateLimiter over both rpm and tpm, and 429/529 backoff honoring Retry-After.
- **Pricing table drift makes old cassettes report wrong cost.** → pricing_version stamped in every CallRecord; replay costs with capture-time prices by default, or --reprice against current; multiplier-free fair_tokens headline is price-independent.
- **A reasoning-model cost comparison unfairly frames fan-out as expensive because thinking tokens bill as output.** → Model tier fixed across all engines (existing invariant); when reasoning is enabled, thinking-token output is reported as a separate line and a standing caveat explains reasoning-substitutes-for-fan-out.

#### Open questions
- Which concrete model IDs and $/Mtok values ship in pricing.py, and how is the table refreshed (manual dated commits vs a pull from Anthropic's pricing page at capture time)?
- Should the shared system prompt expose a single stable cache breakpoint so the OPTIONAL caching-axis benchmark is realistic, and where exactly does that cache_control block sit relative to the per-agent role text?
- For --strict-order replay, how are legitimately-repeated identical prompts (orchestrator re-sweeps) distinguished from accidental prompt drift — sequence assertion vs digest-count tolerance?
- Do we emit OpenTelemetry GenAI spans in v1 (mapping usage to gen_ai.usage.* attributes) or defer to the viz slice and only expose the mapping helper?
- What default --runs N balances CI cost against CI-width for the real-mode variance claim (5 vs 10), and do we gate the published margin on a maximum CI half-width?

### 10.3 Observability, Tracing & the Event Stream: the canonical OVB instrumentation contract

_A single append-only WORM event log with a versioned, OTel-GenAI-aligned JSON event contract that all three engines (orchestrator, blackboard, hybrid) emit identically and that the CLI, live UI, and exporters consume. Nine core event types carry a monotonic per-run seq, run_id, engine, span_id and causal parent_span_id, plus gen_ai.* attributes drawn from real Anthropic streaming usage (input, output, cache_creation, cache_read). Transport to the UI is SSE (fits the append-only, server-push, replayable log; no client->server channel needed) with a Last-Event-ID replay cursor, bounded ring-buffer backpressure, and a record/replay cassette layer so the whole demo runs offline and deterministically. Optional OTLP/Langfuse exporters map the same log to spans. The contract is designed so fairness is auditable: the log itself proves only the control model differs._

#### Position and load-bearing constraints

This slice owns the one artifact every other slice depends on: the event. Engines produce it; the CLI, the live D3 UI, the benchmark, the cassette layer, and the exporters consume it. If the schema is loose, fairness claims become unfalsifiable and the UI/CLI drift. So the design goal is a **single, versioned, self-describing JSON event** that is (a) the WORM log line, (b) the SSE frame, (c) the replay record, and (d) the source row for OTLP/Langfuse export — one shape, four consumers, no translation layers.

Three hard constraints shape everything:

1. **WORM + monotonic ordering.** Events are append-only and per-run totally ordered by `seq` (uint, starts at 0). `seq` is the replay cursor and the SSE event id. No event is ever mutated; corrections are new events.
2. **Causality is explicit, not inferred.** Every event carries `span_id` and `parent_span_id`. The UI must render the orchestrator's nested-sweep structure and the blackboard's ripple DAG *from the log alone*, without knowing engine internals. Wall-clock time cannot encode causality (async, mock mode has no real clock), so causality is a first-class field.
3. **Fairness is provable from the log.** Because only the control model may differ, the log must let a reviewer diff two runs and confirm the agent set, task hash, gate, model, and temperature are identical. We put those in `run_started` as a `fairness_digest` (a hash over agents+task+gate+model+temp+seed) so a CI check can assert `orchestrator.fairness_digest == blackboard.fairness_digest == hybrid.fairness_digest`.

#### The event envelope

Every event is a flat JSON object with a fixed envelope plus a typed `attributes` bag. I deliberately keep the envelope small and put GenAI/domain fields in `attributes` so the envelope never versions for a new attribute.

```
{ v, seq, ts_wall_ns, ts_mono_ns, run_id, engine, type,
  span_id, parent_span_id, agent, attributes{...} }
```

- `v`: contract version, currently `"ovb.events/1"`. Consumers reject unknown major.
- `seq`: uint64, per-run monotonic, gap-free. Doubles as SSE id and replay cursor.
- `ts_wall_ns` / `ts_mono_ns`: wall clock (for humans) vs a monotonic source. **In mock mode both are synthesized deterministically** (a virtual clock advanced by `usage.total` — mirroring the existing `latency_for`) so replays are byte-identical and never flake. Real mode uses `time.time_ns()` and `time.perf_counter_ns()`. The `deterministic` bool in `run_started` tells consumers which regime they are in.
- `engine`: `orchestrator | blackboard | hybrid`.
- `span_id` / `parent_span_id`: 8-byte hex (OTel-compatible). Root events (`run_started`) have `parent_span_id=null`.
- `agent`: convenience denormalization of the acting agent name (null for run-level events).

This is the WORM line (one JSON object per line, JSONL). It is also exactly the SSE `data:` payload. No separate wire format.

#### The nine event types and their span model

I map the emitted events onto an OTel-GenAI span tree. The mapping is the key design decision, because it lets the same log drive both the bespoke UI and standard OTLP tooling.

**Span hierarchy** (each `*_started`/`*_finished` pair is one span; single events are span-events on the enclosing span):

- `run_started` / `run_finished` → **root span**, `gen_ai.operation.name = invoke_workflow`. Attributes: `fairness_digest`, `deterministic`, `seed`, `model`, `temperature`, `task_hash`, `gate_name`, `agent_roster` (names+owns+subscribes), `engine_params` (e.g. `max_rounds`/`max_steps`/hybrid bound). `run_finished` adds `steps`, `consistent`, `stop_reason` (`gate_satisfied | fixpoint | max_steps | error`), and roll-up `usage`, `cost_usd`, `wall_ms`.
- `agent_activated` → span-event opening an **agent span**, `gen_ai.operation.name = invoke_agent`, `gen_ai.agent.name = <agent>`. Attributes: `trigger` (the existing `why`: `"seed: scope posted" | "scope changed" | "sweep 2"`), `view_hash` (hash of the state snapshot the agent saw — proves isolation/ordering), `activation_id`. Parent = current sweep span (orchestrator) or the writer's ripple span (blackboard) or the bounded-blackboard subroutine span (hybrid).
- `llm_call_started` → child span under the agent span, `gen_ai.operation.name = chat`, span name `chat {model}`. Attributes: `gen_ai.provider.name = anthropic`, `gen_ai.request.model`, `gen_ai.request.temperature`, `gen_ai.request.max_tokens`, `gen_ai.request.stream`, plus `prompt_hash` and `prompt_chars` (never raw prompt by default — see redaction).
- `llm_token_delta` → span-event on the llm span. Attributes: `text_delta` (redactable), `output_tokens_cum`, `cache_read_input_tokens_cum`, `cache_creation_input_tokens_cum`. **Critical correctness detail from the API research: Anthropic's `message_delta` usage is CUMULATIVE, not incremental.** The emitter stores cumulative and computes per-delta increments for the UI's live token counter; naive summation double-counts. In mock mode, deltas are synthesized by chunking `expect` text into N pieces for a realistic streaming animation.
- `llm_call_finished` → closes the llm span. Attributes carry the **real** final usage from `message_start.usage` + terminal `message_delta.usage`: `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cache_creation.input_tokens`, `gen_ai.usage.cache_read.input_tokens`, `gen_ai.response.id`, `gen_ai.response.finish_reasons`, plus derived `cost_usd` (priced from a per-model table, cache-read tokens billed at the discounted rate) and `latency_ms` (wall in real mode; synthesized in mock).
- `state_write` → span-event on the agent span. Attributes: `field`, `old`, `new`, `write_id`. This IS the existing WORM `Event`, now unified into the one log. Parent linkage is what turns the blackboard into a DAG: the next `agent_activated` caused by this write carries `parent_span_id = state_write.span_id`'s agent span, and its `trigger` names this field.
- `agent_retriggered` → span-event (blackboard/hybrid only) recording that a write enqueued a subscriber. Attributes: `field`, `subscriber`, `caused_by_write_id`. This is the causal edge the UI draws as an animated arrow; it is emitted at enqueue time even though the activation happens later, so the UI can show "pending ripple."
- `gate_checked` → span-event on the root span. Attributes: `gate_name`, `result` (bool), `unsatisfied_predicates` (list, e.g. `["timeline_weeks != scope*2"]`). Emitted after every step by all engines identically — this is where a reviewer confirms the *same* gate ends every run, the linchpin of the fairness claim.

Note `agent_retriggered` and the orchestrator's sweep have no analog in each other by design; the orchestrator emits a synthetic `sweep` span (child of root, `gen_ai.operation.name = plan`) so its fixed-order structure is visible without inventing ripple edges. The hybrid emits a `bounded_blackboard` subroutine span (child of the orchestrator step that invoked it) whose subtree is a normal blackboard trace — first-class, not bolted on.

#### Emitter API (engines) and the tap

The current `Recorder` is retained as the **aggregation view** but is fed by a new `EventBus`. Engines emit via a thin, typed façade so a bad event can't be constructed:

```python
bus = EventBus(run_id, engine, clock, sinks=[JsonlSink(path), RingBufferSink(cap=4096)])
with bus.run_span(fairness_digest=..., model=..., temperature=0.0, seed=7,
                  task_hash=..., gate_name="is_consistent", roster=...) as run:
    with run.agent_span("Budget", trigger="scope changed", view=state) as ag:
        with ag.llm_span(model, temperature=0.0, prompt=p) as call:
            for delta in stream: call.token_delta(delta)  # handles cumulative usage
            call.finished(usage, response_id, finish_reasons)
        ag.state_write("budget_k", old, new)         # emits state_write
        run.retrigger("budget_k", subscriber="...", write_id=...)  # blackboard only
    run.gate_checked("is_consistent", ok, unsatisfied)
```

Context managers guarantee paired started/finished, correct `parent_span_id` from an explicit span stack (not thread-locals — the blackboard is single-threaded but the async real-mode path is not), and monotonic `seq` from a single atomic counter. **The engines' control logic is untouched**; instrumentation is additive wrapping, preserving the "only the control model differs" invariant. The existing `blackboard.py`/`orchestrator.py` `record_write`/`record_call` calls become `ag.state_write(...)` / implicit on span close.

`Usage` gains four fields (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`) with a back-compat `prompt_tokens`/`completion_tokens` alias, and a `cost_usd(model)` method reading a `PRICES` table.

#### Transport to the UI: SSE, not WebSocket

**Decision: Server-Sent Events.** The traffic is strictly server→client, append-only, text/JSON, and needs cheap replay — which is exactly SSE's model. SSE gives us native event ids (`id: <seq>`) and automatic `Last-Event-ID` reconnection, so replay-from-log is a built-in browser feature, not custom code. WebSocket buys a client→client channel we don't need and forces us to hand-roll resumption. The only WS advantage (binary/duplex) is irrelevant here. The UI's controls (play/pause/scrub) act on the *client-side* buffer, not the transport, so no upstream channel is required.

Endpoints (a ~120-line stdlib `http.server` + `asyncio` app, zero deps):
- `GET /runs` → list of run_ids with summaries.
- `GET /runs/{id}/events?from={seq}` → SSE stream. On connect, replays log from `from` (or `Last-Event-ID`+1), then tails live. Each frame: `id: {seq}\nevent: {type}\ndata: {json}\n\n`. A `event: heartbeat` every 15s keeps proxies open and lets the client detect stalls.
- `GET /runs/{id}/log.jsonl` → the raw WORM file for offline/CLI use.

**Backpressure.** The producer (engine, possibly faster than the browser in mock mode) writes to a bounded per-connection ring buffer (`RingBufferSink`, cap 4096). The JSONL file sink is the durable source of truth and is never dropped. If a slow client's ring overflows, the server does **not** block the engine and does **not** silently drop: it closes the SSE connection with a final `event: lag {"dropped_after": seq}` frame; the browser auto-reconnects with `Last-Event-ID` and re-reads the gap from the JSONL file. This makes the file the backpressure relief valve and guarantees the client can always reconstruct a gap-free stream. Because `seq` is gap-free, the client asserts `seq == last+1` and requests a replay on any gap — the invariant that makes lossy live transport safe.

#### Record/replay cassette layer

Fairness with real, nondeterministic models requires temp=0 + N runs + variance + replay. The cassette layer sits at the `ClaudeLLM` boundary, keyed by a hash of `(model, temperature, system, prompt, seed)`:

- **record mode**: real API calls; each streamed response (all SSE chunks incl. `message_start`, `content_block_delta`, `message_delta` usage, `message_stop`) is serialized verbatim to `cassettes/{hash}.jsonl`.
- **replay mode**: the recorded chunk stream is re-emitted with synthetic inter-chunk delays, so `llm_token_delta` events and the UI animation are reproduced without a key — the demo runs offline, deterministically, yet exercises the *real* streaming code path and *real* token/cost numbers.
- **mock mode**: no API, deterministic synthetic stream from `expect`.

This gives three regimes on one code path — the repo's core honesty requirement. A `--regime {mock,replay,record}` flag selects; CI runs `replay` against committed cassettes so token/cost assertions are pinned. N-run variance harness records N cassettes at temp=0, reports mean/stdev/CI of calls/tokens/cost/latency per engine, so margins are honest.

#### Exporters

An `OtlpExporter` and `LangfuseExporter` consume the JSONL log post-hoc (or via a tee sink live) and translate the span tree — which already carries `gen_ai.*` attributes — into OTLP spans / Langfuse traces. Because the event model was designed on the OTel GenAI conventions (operation names `invoke_workflow`/`invoke_agent`/`chat`/`plan`/`execute_tool`, `gen_ai.usage.*`, `gen_ai.provider.name`), this is a near-mechanical field rename, not a semantic remodel. Exporters are optional and dependency-gated; the core repo stays stdlib-only.

#### Redaction and prompt-injection blast radius

Because shared state is the blackboard's attack surface, the log defaults to **hashes not payloads**: `prompt_hash`, `view_hash`, `text_delta` gated behind `OVB_LOG_CONTENT=1`. `state_write` old/new values ARE logged (they're the domain data and the audit point), but a `redact_fields` allowlist can hash sensitive fields. This lets the security narrative show, concretely, that a poisoned `state_write` ripples to N subscribers — the WORM log *is* the blast-radius forensic record, and `agent_retriggered` edges quantify the radius.

#### Why this is fair and honest by construction

The `gate_checked` events prove the same deterministic gate ends every run. The `fairness_digest` proves identical agents/task/model/temp/seed across engines. The per-`llm_call_finished` real usage means no number is hardcoded — the existing 7-calls/511-tok vs 12/908 result re-derives from counting events. And because the orchestrator's wasted final confirming sweep shows up as agent spans with empty `state_write` sets, the "wasted work" the topology comparison hinges on is visible and auditable rather than asserted.

#### Interfaces & contracts
##### Contract version
`v = "ovb.events/1"`. Consumers MUST reject unknown major version. New attributes are additive within a major.

##### Event envelope (JSONL line / SSE data payload — identical bytes)
```jsonc
{
  "v": "ovb.events/1",
  "seq": 42,                    // uint64, per-run, gap-free, == SSE id
  "run_id": "01JABC...",        // ULID
  "engine": "blackboard",       // orchestrator | blackboard | hybrid
  "type": "llm_call_finished",  // one of the 9 core types
  "span_id": "a1b2c3d4e5f60718",       // 8-byte hex
  "parent_span_id": "0011223344556677",// null on run_started
  "agent": "Budget",            // null for run-level events
  "ts_wall_ns": 1751400000000000000,
  "ts_mono_ns": 1234567,        // deterministic virtual clock in mock/replay
  "attributes": { /* type-specific, see below */ }
}
```

##### Per-type `attributes` (OTel GenAI aligned)
```jsonc
// run_started  (root span; gen_ai.operation.name=invoke_workflow)
{ "deterministic": true, "seed": 7, "regime": "replay",
  "gen_ai.request.model": "claude-sonnet-5", "gen_ai.request.temperature": 0.0,
  "fairness_digest": "sha256:...",       // hash(agents+task+gate+model+temp+seed)
  "task_hash": "sha256:...", "gate_name": "is_consistent",
  "agent_roster": [{"name":"Scope","owns":["scope"],"subscribes":["max_scope"]}, ...],
  "engine_params": {"max_steps": 100} }

// agent_activated  (opens agent span; gen_ai.operation.name=invoke_agent)
{ "gen_ai.agent.name": "Budget", "activation_id": 5,
  "trigger": "scope changed", "view_hash": "sha256:..." }

// llm_call_started  (chat span; span name "chat {model}")
{ "gen_ai.provider.name": "anthropic", "gen_ai.request.model": "claude-sonnet-5",
  "gen_ai.request.temperature": 0.0, "gen_ai.request.max_tokens": 256,
  "gen_ai.request.stream": true, "prompt_hash": "sha256:...", "prompt_chars": 214 }

// llm_token_delta  (span-event; CUMULATIVE usage per Anthropic message_delta)
{ "text_delta": "adjust",              // omitted unless OVB_LOG_CONTENT=1
  "output_tokens_cum": 12,
  "cache_read_input_tokens_cum": 1800, "cache_creation_input_tokens_cum": 0 }

// llm_call_finished  (closes chat span; REAL usage)
{ "gen_ai.usage.input_tokens": 214, "gen_ai.usage.output_tokens": 18,
  "gen_ai.usage.cache_creation.input_tokens": 0,
  "gen_ai.usage.cache_read.input_tokens": 1800,
  "gen_ai.response.id": "msg_01...", "gen_ai.response.finish_reasons": ["end_turn"],
  "cost_usd": 0.000123, "latency_ms": 642.0 }

// state_write  (span-event; the WORM audit row)
{ "field": "budget_k", "old": null, "new": 120, "write_id": 3 }

// agent_retriggered  (blackboard/hybrid; the causal ripple edge)
{ "field": "budget_k", "subscriber": "Scope", "caused_by_write_id": 3 }

// gate_checked  (span-event on root; the fairness linchpin)
{ "gate_name": "is_consistent", "result": false,
  "unsatisfied_predicates": ["timeline_weeks != scope*2"] }

// run_finished  (closes root span)
{ "stop_reason": "gate_satisfied",    // gate_satisfied|fixpoint|max_steps|error
  "steps": 7, "consistent": true,
  "usage": {"input_tokens": 1490, "output_tokens": 126,
            "cache_creation.input_tokens": 0, "cache_read.input_tokens": 9000},
  "cost_usd": 0.0021, "wall_ms": 4120.0 }
```

##### Emitter façade (Python, `ovb/instrumentation.py`)
```python
class EventBus:
    def __init__(self, run_id: str, engine: str, clock: Clock,
                 sinks: list[Sink]): ...
    def run_span(self, *, fairness_digest, model, temperature, seed,
                 task_hash, gate_name, roster, engine_params) -> "RunSpan": ...

class RunSpan:                     # context manager -> run_started/run_finished
    def agent_span(self, agent, *, trigger, view) -> "AgentSpan": ...
    def retrigger(self, field, *, subscriber, write_id) -> None: ...
    def gate_checked(self, name, result, unsatisfied) -> None: ...

class AgentSpan:                   # context manager -> agent_activated + close
    def llm_span(self, model, *, temperature, prompt) -> "LlmSpan": ...
    def state_write(self, field, old, new) -> int:   # returns write_id
        ...

class LlmSpan:                     # context manager -> llm_call_started/finished
    def token_delta(self, chunk) -> None:            # handles CUMULATIVE usage
        ...
    def finished(self, usage: "Usage", response_id, finish_reasons) -> None: ...

class Sink(Protocol):
    def emit(self, event: dict) -> None: ...
class JsonlSink(Sink):      ...   # durable WORM file, never drops
class RingBufferSink(Sink): ...   # bounded (cap=4096) live tail for SSE
class OtlpExporter(Sink):   ...   # optional, gen_ai.* -> OTLP spans
class LangfuseExporter(Sink): ...

class Clock:                      # real: perf_counter_ns; mock: virtual, +=usage.total
    def wall_ns(self) -> int: ...
    def mono_ns(self) -> int: ...
```

##### Usage struct (extended, `ovb/llm.py`)
```python
@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    # back-compat aliases: prompt_tokens->input_tokens, completion_tokens->output_tokens
    def cost_usd(self, model: str) -> float: ...   # cache_read billed at discount
```

##### SSE transport (server, stdlib asyncio)
```
GET /runs                         -> [{run_id, engine, stop_reason, ...}]
GET /runs/{id}/events?from={seq}  -> text/event-stream
      frame: "id: {seq}\nevent: {type}\ndata: {json}\n\n"
      replays from max(from, Last-Event-ID+1), then tails live
      heartbeat: "event: heartbeat\ndata: {}\n\n" every 15s
      on overflow: "event: lag\ndata: {\"dropped_after\": seq}\n\n" then close
GET /runs/{id}/log.jsonl          -> raw WORM file (gap-fill on reconnect)
```
Client invariant: assert `seq == last+1`; on gap, refetch via `?from=last+1`.

##### Cassette layer (`ovb/cassette.py`)
```python
key = sha256(f"{model}|{temperature}|{system}|{prompt}|{seed}")
#### cassettes/{key}.jsonl = verbatim ordered Anthropic stream chunks
class CassetteLLM:                # wraps ClaudeLLM; --regime record|replay
    def complete_stream(self, system, prompt, expect="") -> Iterator[Chunk]: ...
```

##### File touch-list
- `ovb/instrumentation.py` — EventBus/spans/sinks/Clock (rewrites Recorder as an aggregation view over the log).
- `ovb/llm.py` — extend `Usage`; `ClaudeLLM.complete_stream` yielding real chunks with cumulative-usage handling; `PRICES` table.
- `ovb/cassette.py` — new; record/replay.
- `ovb/blackboard.py` / `ovb/orchestrator.py` / `ovb/hybrid.py` — swap `record_*` for span façade (control logic unchanged).
- `web/server.py` — new; SSE app.
- `web/live.html` + D3 — new; consumes SSE.
- `ovb/exporters.py` — new; optional OTLP/Langfuse sinks.
- `docs/EVENT-CONTRACT.md` — normative spec of the above.
- `tests/test_events.py` — schema, gap-free seq, paired spans, fairness_digest equality, cumulative-usage non-double-count.

#### Key decisions
- **SSE over WebSocket for the UI transport.** — Traffic is server->client, append-only, JSON, and needs cheap resumable replay. SSE gives native event ids + Last-Event-ID auto-reconnection, so replay-from-log is a browser built-in. The UI's play/pause/scrub act on a client-side buffer, so no upstream channel is needed. WebSocket's duplex/binary advantages are irrelevant here and would force hand-rolled resumption. _(alt: WebSocket (rejected: needless duplex, manual resume); long-poll (rejected: no streaming animation); gRPC (rejected: deps, browser friction).)_
- **One JSON event shape is simultaneously the WORM line, SSE frame, replay record, and exporter source row.** — Eliminates translation layers and schema drift between CLI and UI; the log is the single source of truth. A small fixed envelope + typed attributes bag means new fields never version the envelope. _(alt: Separate log format vs wire format (rejected: drift risk, double maintenance).)_
- **Explicit span_id/parent_span_id causal edges on every event, plus a dedicated agent_retriggered event.** — The UI must render the orchestrator's nested sweeps and the blackboard's ripple DAG from the log alone. Wall-clock cannot encode causality (async + deterministic mock clock). Explicit parent links make the DAG reconstructable and the security blast-radius quantifiable. _(alt: Infer causality from timestamps/order (rejected: wrong under async and mock virtual time).)_
- **Align the span model to OTel GenAI operation names and gen_ai.usage.* attributes from day one.** — Makes OTLP/Langfuse export a mechanical field rename rather than a remodel, and makes the repo legible to standard LLM-observability tooling. invoke_workflow/invoke_agent/chat/plan/execute_tool are exactly the emitted structure. _(alt: Bespoke attribute names + adapter later (rejected: guarantees an impedance-mismatch adapter and lossy export).)_
- **Three regimes (mock / replay / record) on ONE streaming code path via a cassette layer keyed by (model,temp,system,prompt,seed).** — Delivers the repo's core honesty requirement: offline reproducible demos with REAL token/cost numbers, plus a temp=0 N-run variance harness for honest margins. CI pins numbers against committed cassettes. _(alt: Mock-only (rejected: not real) or live-only (rejected: needs keys, flaky, non-reproducible).)_
- **JSONL file sink is the durable source of truth; live SSE ring buffer may drop, and the client gap-fills from the file.** — Decouples engine speed from browser speed without blocking the engine or silently losing events. Gap-free seq lets the client detect any loss and refetch, so lossy live transport is provably safe. _(alt: Block producer on slow client (rejected: stalls engine); unbounded buffer (rejected: OOM); silent drop (rejected: corrupts the audit/fairness claim).)_
- **Log hashes (prompt_hash/view_hash) by default; raw content only behind OVB_LOG_CONTENT=1.** — Shared state is the blackboard's injection surface; the WORM log becomes the blast-radius forensic record while defaulting to minimal sensitive payload exposure. state_write old/new stay logged as the audit point. _(alt: Always log full prompts (rejected: leakage, bloat) or never (rejected: kills debuggability/security narrative).)_
- **Handle Anthropic message_delta usage as CUMULATIVE, computing per-delta increments for the live counter.** — The API returns cumulative cache/output token counts in message_delta; naive summation double-counts (a documented real-world bug class). The emitter stores cumulative and derives increments so the live token animation and final totals are both correct. _(alt: Treat deltas as incremental (rejected: inflates token/cost numbers, breaks fairness).)_

#### Risks
- **Instrumentation subtly changes engine behavior (e.g. context managers reorder emits vs writes), silently breaking the 'only control model differs' fairness invariant.** → Additive wrapping only; state_write is emitted at the exact point state is mutated. A CI test asserts fairness_digest equality across engines and that replaying the log reproduces identical final state/usage as the in-process recorder.
- **Cumulative-usage mishandling reintroduces token double-counting, corrupting the headline token comparison.** → Emitter stores cumulative-only and derives increments in one place; unit test feeds a recorded Anthropic stream and asserts summed increments == final message_delta cumulative == llm_call_finished totals.
- **SSE ring-buffer overflow drops events and the client fails to notice, showing a corrupted DAG.** → Gap-free seq + client-side seq==last+1 assertion + lag frame + JSONL gap refetch. Test simulates a slow client and asserts the reconstructed stream from file is byte-identical.
- **OTel GenAI conventions are still evolving (v1.41.x); attribute names may shift, breaking exporters.** → Pin a conventions version in EVENT-CONTRACT.md; isolate all gen_ai.* naming to a single mapping module so a convention bump is a one-file change. Core envelope is convention-independent.
- **Deterministic virtual clock in mock/replay makes latency numbers look real but are synthetic, misleading a reader into citing them as measured.** → run_started.deterministic=true and regime are prominent; UI badges 'synthetic latency' in mock/replay; only record regime surfaces measured wall latency; docs state this explicitly.
- **Prompt/state content leaking into the WORM log (which is committed for cassettes) exposes sensitive scenario data.** → Hash-by-default; OVB_LOG_CONTENT opt-in; redact_fields allowlist; cassette-scrubbing step in the record path and a CI grep guard against raw-prompt fields in committed logs.

#### Open questions
- Cost table maintenance: prices per model drift. Pin a PRICES dict with an as-of date and a CI reminder, or fetch at runtime? Leaning static+dated for reproducibility.
- Cassette key stability: prompts embed the full state dict (order-sensitive). Do we canonicalize (sorted keys) the state before hashing so trivially-reordered dicts hit the same cassette? Proposed: yes, canonical JSON before hashing.
- Should agent_retriggered be emitted at enqueue time (shows pending ripples, but an event whose activation may never run if the gate fires first) or at activation time (cleaner causality, loses the 'pending' UI affordance)? Current design: enqueue time, with the UI marking unrealized ripples.
- Multi-run comparison view: stream two runs over one SSE connection (multiplex with run_id) or two connections? Two connections is simpler and lets each replay independently; revisit if the browser connection cap bites.
- How much of the real Anthropic error taxonomy (429/overloaded/streaming abort) to model as run_finished stop_reason=error vs a dedicated error event? Proposed: dedicated non-core `error` span-event so the 9 core types stay clean.
- Do we want a compaction/gen_ai.conversation.compacted signal now, or defer until a scenario actually compacts context? Defer.

### 10.4 Dynamic Visualization & UI: Live Side-by-Side Control-Model Dashboard (ovb-viz)

_A cassette-first live dashboard that replays the same reconciliation task through Orchestrator, Blackboard, and Hybrid engines in synchronized side-by-side panels. Stack: FastAPI + SSE backend that owns a deterministic virtual clock and streams a versioned OTel-aligned event envelope; a Vite + React 18 + TypeScript + D3 (force + scales only) frontend with a Zustand event-reducer store. Three topology-specific canvases (orchestrator timeline, blackboard force graph with write-cascade re-trigger animation, hybrid nested), a live meter rail (in/out/cache tokens, USD, latency, calls, wasted calls), a WORM scrub bar, and a per-agent cost + convergence chart. Runs with zero API key from recorded cassettes; the exact same SSE stream is emitted from live Claude runs so demo and production frames are byte-identical. The money shot is the synchronized dual-panel "cost-to-converge race" where the orchestrator keeps re-sweeping while the blackboard's cascade dies out early, meters diverging in real time._

#### Scope and the one design constraint that dominates everything

My slice renders three control models *in action* on the same task, side-by-side, live, and — critically — reproducibly without an API key. The existing `viz.py` is a post-hoc static HTML dump: it takes finished `Recorder` objects and formats tables. That is the wrong shape for "in action." The core architectural move is to **invert the data flow from pull-at-end to push-per-event**: both engines already call `rec.record_call` / `rec.record_write` at exactly the moments that matter, so I tap those two call sites through an emitter and turn each into a wire event. Everything downstream (backend fan-out, frontend animation, meters, scrub) is a pure function of that event stream. This is what makes the mock cassette and the live Claude run produce *identical UI frames*: the frontend never knows which one it is watching.

##### Fairness is a UI invariant, not just a backend one

The non-negotiable fairness principle has a visualization corollary I enforce structurally: the three panels share **one event schema, one meter component, one color-per-agent map, one clock**. The only thing that differs across panels is the *canvas* component chosen by `engine` tag. There is no orchestrator-specific meter, no blackboard-specific cost formula. If a viewer sees the blackboard "win," it is because fewer `call` events arrived — never because the chart flattered it. I also render the `wasted_calls` counter identically for both, so the orchestrator's confirming no-op sweep is visible, not hidden.

#### Stack decision (opinionated)

**Backend: FastAPI + Server-Sent Events (SSE), not WebSockets.** The stream is strictly server→client, append-only, and text/JSON — exactly SSE's shape. SSE gives us free auto-reconnect with `Last-Event-ID`, which maps perfectly onto our monotonic `seq`: a dropped connection resumes mid-run by replaying the WORM tail. WebSockets would add a bidirectional protocol we don't need and lose the native replay semantics. The only client→server actions (play/pause/seek/speed/select-run) are low-frequency and go over plain `POST` control endpoints, not the stream.

**Frontend: Vite + React 18 + TypeScript + D3 (modules `d3-force`, `d3-scale`, `d3-shape`, `d3-selection` only — not the monolith).** This is a flagship reference artifact for senior engineers, so I want the code to be idiomatic and forkable, not a 2000-line vanilla `<script>`. React gives a clean component tree and lets three panels subscribe to slices of one store without re-rendering each other. D3 owns *only* the force simulation and scales; React owns the DOM/SVG so we never fight D3 over element ownership (the well-known "React renders, D3 calculates" split). I reject a heavier graph lib (Cytoscape/vis) because the blackboard graph is tiny (5 state nodes + 4 agents) and the *animation semantics* (pulse-on-write, re-trigger edge flash) are bespoke — a general graph lib would be more code, not less.

**Transport format: newline-delimited JSON events with an OTel-GenAI-aligned attribute vocabulary.** Each `call` event carries `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, plus Anthropic's cache fields `cache_creation_input_tokens` / `cache_read_input_tokens`. Aligning to the published `gen_ai.*` semantic conventions means the cassettes double as OTel fixtures and the numbers have an obvious provenance for the audience.

##### The cassette is the source of truth

A cassette is a gzipped JSONL file: the ordered event stream for one `(engine, task, model, seed)` run, plus a header frame. `record` mode wraps `ClaudeLLM` and, per real call, captures the **full Anthropic `usage` object** — and here the web research matters: in streaming, `message_start` and the final `message_delta` both report cumulative `cache_creation_input_tokens`/`cache_read_input_tokens`, so the recorder must read usage **once from the terminal `message_delta`** (or the non-streaming `message.usage`) and never sum the two, or every cache number doubles. The cassette stores the settled per-call usage, so replay is immune to that bug by construction. `replay` mode reads the cassette and re-emits events on the virtual clock. Because latency is a recorded field, replay reproduces the real run's *pacing*, not just its totals — the race animation is faithful.

#### The event contract (what the whole UI is a function of)

Two engine call sites already exist. I introduce an `Emitter` protocol that `Recorder` delegates to, so engines are untouched except for construction. Event kinds:

- `run_started` — header: engine, task hash, model, seed, agent roster with owns/subscribes (this seeds the graph topology), gate description.
- `agent_scheduled` — an agent is enqueued (blackboard) or reached in the sweep order (orchestrator). Carries `trigger` (the existing field: `"seed: scope posted"`, `"sweep 2"`, `"scope changed"`). This is the event that drives the *anticipation* animation before the call resolves.
- `call_started` — agent begins; UI shows a spinner/pulse on that agent node.
- `state_write` — one field old→new (the WORM record). Drives the graph node pulse + cascade edges.
- `call_finished` — carries settled `usage` (all four token classes), `latency_ms`, `changed`, `writes`, cumulative aggregates. Drives meters.
- `gate_checked` — deterministic `is_consistent` result after the call. When `true`, the convergence marker fires. This makes the *gate*, not the LLM, visibly the thing that ends the run.
- `run_finished` — final state, totals, converged flag.

Every event has `seq` (monotonic per run, used as SSE `id:`), `t_virtual_ms` (position on the shared clock), `engine`, and `run_id`. `t_virtual_ms` is the cumulative sum of recorded `latency_ms` within that engine's run — this is the axis that lets two panels share a clock.

#### Synchronized clock and the compare mode

Compare mode is the flagship view: orchestrator and blackboard (optionally hybrid) run as **separate cassettes replayed against one shared virtual clock** owned by the backend `Conductor`. A single wall-clock tick advances `t_virtual_ms` for all panels together at the current playback speed (0.25×–8×). Each panel emits its next event when its own `t_virtual_ms` cursor is reached. Because the blackboard finishes at a smaller `t_virtual_ms`, its panel visibly *stops* while the orchestrator keeps grinding — the meters freeze on one side and climb on the other. That divergence, on a shared time axis, is the whole thesis rendered as motion. Crucially the clock is virtual and deterministic: pause/seek/replay land on exact event boundaries, so screenshots and CI snapshots are stable.

#### Frontend component tree and state

```
<App>
  <RunControls>            // play/pause/speed/seek, engine multiselect, task picker
  <SharedClock>            // the synchronized t_virtual scrubber (WORM-backed)
  <CompareGrid>           // 1..3 columns, one per selected engine
    <EnginePanel engine>   // subscribes to store slice for this run_id
      <MeterRail>          // the live meters (shared component)
      <TopologyCanvas>     // switches on engine:
         <OrchestratorTimeline/>   // supervisor→agent swimlane, sweep bands
         <BlackboardGraph/>        // d3-force shared-state graph
         <HybridCanvas/>           // orchestrator shell w/ embedded bounded BB
  <ConvergencePanel>       // dual line chart: gate-distance vs t_virtual
  <CostBreakdown>          // per-agent stacked bars, in/out/cache split
  <WormInspector>          // append-only write log, click-to-seek
```

**State management: Zustand with an event-reducer core.** One store; the reducer is `applyEvent(state, event)` — a pure fold over the stream, identical to what a Redux setup would use but with far less ceremony. This matters because **scrubbing is just re-folding**: to seek to `seq=k`, reset to the header snapshot and replay events `0..k` through the same reducer. No separate "historical state" code path exists, which kills a whole class of live-vs-replay divergence bugs. The store keeps, per `run_id`: the reconstructed shared-state dict, agent statuses (idle/scheduled/running/done), rolling aggregates (tokens by class, USD, latency, calls, wasted), the graph node/edge model, and the event log for the scrubber. Selectors are memoized per panel so a `state_write` in the blackboard panel never re-renders the orchestrator timeline.

Cost is computed client-side from tokens via a per-model price table (`$/Mtok` for input, output, cache-write, cache-read) shipped as JSON, so the USD meter reflects real cache economics — cache reads showing up as near-free is a teaching moment the dashboard should make vivid.

#### The three canvases

**OrchestratorTimeline** — a swimlane per agent plus a supervisor lane at top. Time flows left→right on `t_virtual_ms`. Each call is a block in the agent's lane; the supervisor lane draws the fixed `Scope→Budget→Timeline→Risk` routing arrow that "walks" the roster each sweep. Sweeps are shaded vertical bands; the final no-op sweep is rendered in a muted "wasted" hatch so the confirming pass is unmissable. A running token tally rides the right edge.

**BlackboardGraph** — `d3-force` layout: 5 state-field nodes (`scope`, `max_scope`, `budget_k`, `timeline_weeks`, `risk`) in the center, 4 agent nodes around them. Edges: solid *owns* edges (agent→field it writes) and dashed *subscribes* edges (field→agent it re-triggers). Forces: `forceManyBody` repulsion, `forceLink` on owns edges, `forceCenter`, and a weak `forceRadial` pinning fields inward / agents outward for a stable, readable ring. On `state_write`: the field node pulses and flashes its value old→new; then each dashed subscribe edge to a dependent agent **animates a traveling particle** (the re-trigger), and that agent lights up as `scheduled`. This is the cascade made literal — you watch scope's change ripple to Budget, Timeline, Risk, and you watch it *die out* when writes stop producing changes. The gate node (a distinct diamond) turns green on `gate_checked=true`.

**HybridCanvas** — the orchestrator swimlane as the outer shell, but one supervisor step expands into an **inset bounded-blackboard mini-graph** that runs its own capped cascade to a local fixpoint, then collapses back and returns control to the sweep. Visually this is the thesis of hybrid-as-first-class: you see the orchestrator's determinism on the outside and the blackboard's local reactivity on the inside, with the `max_steps` cap drawn as a hard ring the inner cascade cannot cross.

#### The money shot

**"Cost-to-converge race," compare mode, synchronized clock.** Two (or three) panels side by side. A single Play advances the shared clock. Above each panel, a large live **USD + token counter** and a horizontal **cost-fill bar**. As replay runs: the blackboard cascade fires, ripples, and hits the gate early — its bar stops at ~511 tokens while the orchestrator is still on sweep 2; the orchestrator keeps sweeping to a no-op fixpoint, its bar climbing past ~908, its wasted-call counter ticking up on the confirming sweep. The frozen blackboard panel with a green gate diamond next to a still-grinding orchestrator, on one clock, with the token bars at ~1.8× apart, is the single frame that sells the entire repo. A "Ghost/PB" overlay can superimpose the blackboard's finish line onto the orchestrator lane like a racing game's personal-best marker.

#### Honesty rendered in the UI

Because the brief demands honesty, the dashboard ships a **"Caveats" toggle** that overlays three annotations sourced from the docs: (1) a *task-shape* switch — flip to the linear `classify→route→answer` task and the orchestrator wins, the same meters now favoring it, proving the tooling isn't rigged; (2) a *blast-radius* overlay on the blackboard graph highlighting that a single poisoned `state_write` reaches every subscriber — prompt-injection surface is literally the edge set; (3) a *variance* band: real runs replay N cassettes at temp=0 and the meters show mean ± stdev, so nondeterminism is visible, not hidden. These aren't footnotes; they're first-class views reachable from the same clock.

#### Reproducibility and CI

Cassettes live in `web/cassettes/*.jsonl.gz`, generated by `demos/record_cassettes.py`. `make viz` runs `uvicorn` serving the built SPA + SSE from cassettes — **no key, no network**. A Playwright snapshot test seeks to fixed `seq` values and asserts meter text + node classes, so the money-shot frame is regression-locked. The same FastAPI app, pointed at `--real`, streams live Claude runs through the identical SSE endpoint — the frontend cannot tell the difference, which is the strongest possible statement that the visualization is honest about what the control models actually do.

#### Interfaces & contracts
##### Wire event envelope (JSONL cassette line == SSE `data:` payload)

```typescript
// web/src/types/events.ts  — versioned, OTel-gen_ai aligned
type EngineTag = "orchestrator" | "blackboard" | "hybrid";

interface Envelope<K extends string, P> {
  v: 1;                      // schema version
  seq: number;               // monotonic per run (used as SSE id:)
  run_id: string;            // f"{engine}:{task}:{model}:{seed}"
  engine: EngineTag;
  t_virtual_ms: number;      // cumulative recorded latency -> shared clock axis
  kind: K;
  data: P;
}

type Event =
  | Envelope<"run_started", RunStarted>
  | Envelope<"agent_scheduled", { agent: string; trigger: string }>
  | Envelope<"call_started", { agent: string }>
  | Envelope<"state_write", { agent: string; field: string; old: unknown; new: unknown }>
  | Envelope<"call_finished", CallFinished>
  | Envelope<"gate_checked", { consistent: boolean; distance: number }> // distance = #unsatisfied clauses
  | Envelope<"run_finished", { state: Record<string, unknown>; converged: boolean; totals: Aggregates }>;

interface RunStarted {
  task: string; task_hash: string; model: string; seed: number;
  gate: string;                                   // human text of is_consistent
  agents: { name: string; owns: string[]; subscribes: string[] }[];
  fields: string[];                               // state schema keys -> graph nodes
}

interface Usage {                                 // mirrors Anthropic usage, OTel names
  "gen_ai.usage.input_tokens": number;            // == message.usage.input_tokens
  "gen_ai.usage.output_tokens": number;
  cache_creation_input_tokens: number;            // read ONCE from terminal delta
  cache_read_input_tokens: number;
}
interface CallFinished {
  agent: string; trigger: string; changed: boolean;
  writes: Record<string, unknown>;
  usage: Usage; latency_ms: number;
  agg: Aggregates;                                // cumulative snapshot after this call
}
interface Aggregates {
  calls: number; wasted: number; writes: number;
  input: number; output: number; cache_write: number; cache_read: number;
  usd: number; latency_ms: number;
}
```

##### Backend Emitter protocol (the only kernel touch-point)

```python
#### ovb/instrumentation.py  — additive; Recorder gains an optional emitter
from typing import Protocol
class Emitter(Protocol):
    def emit(self, kind: str, data: dict) -> None: ...   # stamps v/seq/run_id/engine/t_virtual

class Recorder:
    def __init__(self, engine: str, emitter: "Emitter | None" = None): ...
    # record_call/record_write additionally call self._emitter.emit(...) when set.
    # Engines (orchestrator.py/blackboard.py) are UNCHANGED except Recorder(engine, emitter=e).

#### ovb/emit.py  — two concrete emitters, same interface
class CassetteEmitter(Emitter):   # writes gzip JSONL; used in record/mock mode
    def __init__(self, path: str, run_id: str, t0: float): ...
class SSEEmitter(Emitter):        # pushes onto an asyncio.Queue for the live endpoint
    def __init__(self, queue: "asyncio.Queue[Event]", run_id: str): ...
```

##### FastAPI surface

```
GET  /api/runs                      -> list available cassettes (engine, task, model, seed, n_events)
POST /api/session                   -> {session_id}; body: {engines:[...], task, mode:"replay"|"live"}
GET  /api/stream/{session_id}       -> text/event-stream (SSE); honors Last-Event-ID
POST /api/control/{session_id}      -> {action:"play"|"pause"|"seek"|"speed", seq?, speed?}
GET  /api/cassette/{run_id}         -> full JSONL (frontend prefetch for instant scrub)
```

SSE frame:  `id: <seq>\nevent: <kind>\ndata: <Envelope JSON>\n\n`
Reconnect: client sends `Last-Event-ID: <seq>`; `Conductor` replays cassette tail from `seq+1`.

##### Conductor (shared virtual clock, backend)

```python
#### web/server/conductor.py
class Conductor:
    """Drives 1..3 cassettes against ONE virtual clock for compare mode."""
    def __init__(self, cassettes: list[Cassette], speed: float = 1.0): ...
    async def run(self, out: asyncio.Queue) -> None:
        # advance t_virtual by (wall_dt * speed); flush every event whose
        # t_virtual_ms <= cursor, interleaved across engines, ordered by (t_virtual_ms, run_id).
    def seek(self, seq: int) -> None: ...   # reset cursor; frontend re-folds
```

##### Frontend store reducer (scrub == re-fold)

```typescript
// web/src/store/reducer.ts
interface PanelState { shared: Record<string,unknown>; agents: Record<string,AgentStatus>;
  graph: {nodes: GNode[]; edges: GEdge[]}; agg: Aggregates; log: Event[]; converged: boolean; }
type World = Record<string /*run_id*/, PanelState>;
function applyEvent(w: World, e: Event): World;      // pure fold, used live AND for seek
function foldTo(header: Event, events: Event[], k: number): World; // seek(k)
// Zustand: useStore = create<{world:World; dispatch:(e:Event)=>void; seek:(k:number)=>void}>()
```

##### Files added (my slice)

```
web/server/{app.py,conductor.py,cassette.py,pricing.json}
web/src/{main.tsx,App.tsx}
web/src/store/{store.ts,reducer.ts,selectors.ts}
web/src/panels/{EnginePanel.tsx,OrchestratorTimeline.tsx,BlackboardGraph.tsx,HybridCanvas.tsx}
web/src/components/{MeterRail.tsx,SharedClock.tsx,ConvergencePanel.tsx,CostBreakdown.tsx,WormInspector.tsx,RunControls.tsx,CaveatsOverlay.tsx}
web/src/viz/{force.ts,scales.ts,cascade.ts}     // d3 wrappers, React-owns-DOM
web/cassettes/*.jsonl.gz
ovb/emit.py ; demos/record_cassettes.py ; tests/test_cassette_snapshot.py (Playwright)
Makefile: `viz` target -> build SPA + uvicorn from cassettes (no key)
```

#### Key decisions
- **SSE over WebSockets for the event stream** — Data flow is strictly server->client, append-only JSON; SSE gives native auto-reconnect with Last-Event-ID that maps 1:1 onto our monotonic seq for mid-run resume via WORM tail replay. Control actions are rare and go over plain POST. _(alt: WebSockets (bidirectional, but we'd reimplement replay/resume); long-poll (worse latency, no ordering guarantee).)_
- **React 18 + TypeScript + scoped D3 modules (d3-force/d3-scale/d3-shape only), React owns the DOM** — Flagship artifact must be idiomatic and forkable; component tree lets 3 panels subscribe to store slices independently. D3 computes force layout + scales only, React renders SVG, avoiding the React/D3 DOM-ownership conflict. _(alt: Vanilla JS + full d3 (lighter deps but 2000-line script, poor for a reference repo); Cytoscape/vis (heavier, and our bespoke cascade animation isn't what they optimize for).)_
- **Cassette-first: one JSONL event stream is the source of truth; live and replay emit the identical stream** — Frontend is a pure function of the event stream and cannot tell live from replay -> the visualization is provably honest, and demos run with no key/network. Also makes cassettes double as OTel fixtures. _(alt: Separate live and replay rendering paths (divergence risk, dishonest demos); record only final aggregates (loses per-event pacing needed for the race animation).)_
- **Event-reducer store (Zustand) where scrubbing == re-folding events 0..k through the same applyEvent used live** — One code path for live and historical state kills live-vs-replay divergence bugs; seek is just fold-to-k from the header snapshot. _(alt: Redux (more ceremony, same idea); a separate 'timeline state' structure (duplicate logic, drift).)_
- **Backend-owned virtual clock (Conductor) summing recorded latency_ms as t_virtual_ms, shared across panels** — Deterministic, event-boundary-exact pause/seek gives stable screenshots/CI; a shared axis is what makes the side-by-side divergence legible as motion. _(alt: Client-side wall-clock timers (flaky, unsynchronized panels, unstable snapshots).)_
- **Read Anthropic cache token usage once from the terminal message_delta / message.usage, never sum message_start + message_delta** — Web-verified: streaming reports cumulative cache_creation/cache_read in BOTH message_start and message_delta; summing double-counts and inflates the USD meter. Storing settled usage in the cassette makes replay immune by construction. _(alt: Sum stream deltas (double-counts cache tokens); ignore cache fields (hides the biggest real cost lever).)_
- **Adopt OpenTelemetry gen_ai.* attribute names in the event usage block** — Gives numbers obvious provenance for a senior audience and lets cassettes serve as OTel semantic-convention fixtures with no translation layer. _(alt: Ad-hoc field names (prompt_tokens/completion_tokens) — less interoperable, no external grounding.)_

#### Risks
- **d3-force jitter makes the blackboard graph wander during animation, hurting the money-shot's readability and screenshot stability** → Pin field nodes with forceRadial + fixed fx/fy after initial settle; run the simulation headless for N ticks on run_started, then freeze positions and only animate pulses/particles on writes. Snapshot tests seek to fixed seq with a settled layout.
- **Real LLM nondeterminism (even at temp=0) makes live runs disagree with the shipped cassette, so a live demo contradicts the recorded money shot** → Ship N-run cassettes and render mean +- stdev variance bands in meters; label live mode explicitly; keep the deterministic mock cassette as the canonical money-shot source for CI and README GIFs.
- **Synchronized-clock interleaving across 2-3 cassettes can starve or reorder events under variable playback speed** → Conductor merges by (t_virtual_ms, run_id) key with a stable tie-break and flushes all events <= cursor each tick; seek resets cursor and the frontend re-folds, so ordering is a pure function of the merge key, not of wall-clock timing.
- **Scope creep: the dashboard grows features that implicitly favor one topology, violating the fairness invariant** → Structural guard: single shared MeterRail/pricing/color-map/clock; only the TopologyCanvas differs by engine tag. A lint/test asserts no engine-conditional logic inside meters or cost computation.
- **SSE connection limits (6 per host over HTTP/1.1) break multi-panel compare if each panel opens its own stream** → One SSE connection per session multiplexes all engines (events tagged by run_id); panels are store subscribers, not independent EventSources. Serve over HTTP/2 in the dev container as defense-in-depth.

#### Open questions
- Should the hybrid engine be a third recorded cassette, or synthesized in the UI by nesting a bounded-blackboard cassette inside orchestrator sweep steps? Recording it is more honest but requires the hybrid engine to exist in the kernel first (another slice's deliverable).
- Price table drift: hardcode a pinned pricing.json snapshot for reproducible USD, or fetch current Anthropic prices at record time and stamp them into the cassette header? Leaning toward stamping into the header so historical cassettes stay self-consistent.
- For the caveat 'linear task where orchestrator wins,' do we ship a second task+cassette set now, or gate it behind the task-authoring slice? Affects whether the fairness-proof toggle is live at v1.
- Do we need a full OTLP exporter path (cassette -> real OTel collector) at v1, or is gen_ai.* attribute alignment in the wire format sufficient as a 'fixtures' claim?
- Accessibility of the force-graph cascade for colorblind viewers and screenshot-only contexts: is a parallel textual cascade trace in WormInspector enough, or do we need shape/motion redundancy on every edge flash?

### 10.5 Scenario Catalog + Fair Evaluation Harness for Orchestrator vs Blackboard vs Hybrid

_A five-scenario catalog (each grounded in real data/tools) that fairly separates the three control models on the axes of interdependence vs. independent parallelism, plus a benchmark harness (N runs, temp=0, record/replay cassettes, bootstrap CIs, OTel-aligned metrics) engineered so ONLY the control model differs. Every scenario reuses the existing kernel's Agent/gate/Recorder contract; the harness extends `Recorder` with real Anthropic usage fields (cache tokens) and adds a `Scenario` protocol so engines are scenario-agnostic. Two scenarios are designed to make the blackboard win (interdependence), one to make the orchestrator win (independent fan-out with no back-edges), one code-debug loop that separates them on ripple depth, and one hybrid-only scenario where a bounded blackboard runs as an orchestrator subroutine._

#### Design goals and the fairness contract

My slice answers one question honestly: *for a given real task, which control topology spends the fewest LLM calls/tokens/latency to reach a deterministic correctness gate, and is that margin caused by the topology or by a smuggled policy?* The seed repo already proves the mechanism on one task (blackboard 7 calls/511 tok vs orchestrator 12/908). My job is to (a) generalize the kernel so a *catalog* of real-data scenarios plugs in without touching either engine, and (b) build a harness that measures margins with real Anthropic usage under statistical rigor.

The **fairness contract** is enforced structurally, not by discipline. A `Scenario` supplies exactly: the initial state, the agent roster (`build_agents()`), the deterministic `is_consistent(state)` gate, an `oracle(state)->bool` for external ground truth, and a real data loader. It supplies these *once*; both engines import the identical objects. The three things an engine is allowed to own are: **scheduling order**, **trigger policy** (sweep-all vs subscribe-ripple), and **stop mechanics** (fixpoint vs gate+cap). Nothing else. Concretely: no scenario may hand the orchestrator a different `ORDER` than the natural roster order, and no scenario may give the blackboard a subscription edge the orchestrator's roster doesn't structurally contain. The gate is shared; if I let the blackboard check the gate mid-run but denied the orchestrator an equivalent early-exit, I'd be crediting topology for a one-line policy — so the harness ships an `--orch-early-exit` flag that adds the *same* gate check between sweeps to the orchestrator, and the honest headline number reports **both** orchestrator variants (fixpoint and gate-checked). The blackboard's win must survive the orchestrator also getting the gate.

#### The five scenarios

Each entry below gives: goal · knowledge-sources (agents) · shared state + gate · real data source + oracle · predicted winner + *why (grounded in graph shape)*.

##### S1 — Constraint reconciliation (the seed task, promoted to real data). Predicted winner: BLACKBOARD.
The existing project-plan task, but the constants (`COST_PER_FEATURE_K`, `BUDGET_CAP_K`, `WEEKS_PER_FEATURE`) are loaded from a **real CSV** (a public IT-project estimation dataset, checked into `data/s1_estimates.csv`, so it's reproducible). Agents: Scope, Budget, Timeline, Risk — unchanged. Gate: `is_consistent`. Oracle: the gate *is* the oracle here (a closed-form constraint system) plus an independent brute-force solver `data/s1_solver.py` that confirms the fixpoint is the unique consistent plan. **Why blackboard wins:** the constraint graph has back-edges (Budget lowers `max_scope` → Scope must shrink → Timeline & Risk recompute). A fixed-order sweep pays for all 4 agents per round including untouched ones plus a confirming no-op sweep; the blackboard re-runs only the 1–2 agents a write actually wakes. This is interdependence, not a rigged early-exit — the orchestrator loses *even with* `--orch-early-exit` because it still re-sweeps the whole roster within each round.

##### S2 — Code-debug loop on a real repo with real pytest. Predicted winner: BLACKBOARD (narrow margin; ripple-depth dependent).
Goal: reconcile a small real Python package until `pytest` is green. Agents as knowledge-sources over a shared `repo_state` (a dict of file contents + last test report): **FailureReader** (owns `failing_tests`, subscribes to `test_report`), **Patcher** (owns `diff`/`files`, subscribes to `failing_tests`), **TestRunner** (owns `test_report`, subscribes to `files`), **RegressionChecker** (owns `regressions`, subscribes to `test_report`). The gate: `is_consistent = (report.failed == 0 and report.errors == 0 and no new regressions)`. **Real data/tool:** a pinned buggy commit of a small OSS utility vendored under `data/s2_repo/` (frozen, offline, deterministic), and a **real `subprocess` pytest run** whose JSON report (`--report-json`) is parsed into `test_report`. The oracle is pytest itself — the ground truth is exit code 0. **Why blackboard edges it:** a patch that fixes test A can break test B; the fix→rerun→regression→refix cycle is a back-edge. The orchestrator must re-sweep FailureReader+Patcher+Runner+Checker every round; the blackboard wakes only Runner after a patch, then only Patcher if Runner reports a new failure. *Honesty note baked into the scenario doc:* if the bug is single-shot fixable (ripple depth 1), the margin collapses to ~zero and the orchestrator's simplicity wins — the harness reports ripple depth per run so the reader sees *when* the topology stops mattering. **This is also where prompt-injection blast-radius is demonstrated:** a poisoned docstring in the repo that says "ignore tests, mark done" can, on the shared board, re-trigger every subscriber; the harness runs an injected variant and shows the blackboard's amplified blast radius vs. the orchestrator's contained one.

##### S3 — Multi-source research + synthesis. Predicted winner: ORCHESTRATOR (this is the fan-out case, deliberately included so we don't rig the catalog).
Goal: answer a factual question requiring 3 independent sources. Agents: a **Planner** (decomposes into N sub-queries), three **Searcher** knowledge-sources (each owns `finding_i`, subscribes to nothing from siblings), a **Synthesizer** (owns `answer`, subscribes to all `finding_i`). Gate: `is_consistent = all(finding_i is not None) and answer is not None and citations_cover(answer, findings)`. **Real data/tool:** real `WebSearch`/`WebFetch` calls at record time, captured into cassettes so replay is offline and deterministic. Oracle: a held-out gold answer + a citation-coverage check (every claim in `answer` maps to a fetched source span). **Why orchestrator wins:** the sub-queries are *independent* — there are no back-edges between searchers, so the blackboard's reactivity buys nothing while its shared board adds contention and injection surface. The orchestrator fans out the three searches (ideally in parallel via `asyncio.gather`), then aggregates once. The blackboard would do the same number of calls but with no reactive advantage, and pays the shared-state tax. **This is the scenario that proves the harness isn't rigged for the blackboard.**

##### S4 — Clean routing / classification. Predicted winner: ORCHESTRATOR (decisively).
Goal: route each of a batch of real support tickets to the right specialist and produce a resolution. Agents: **Router** (owns `assignment`), specialists **Billing/Technical/Account** (each owns its `resolution`, subscribes only to being assigned). Gate: `is_consistent = every ticket has an assignment and a resolution from the matching specialist`. **Real data:** a public support-ticket CSV (`data/s4_tickets.csv`). Oracle: labeled gold routing + a resolution-nonempty check. **Why orchestrator wins decisively:** this is a *tree* (one decision, then a hand-off) with zero interdependence. The blackboard's event loop degenerates into a strictly-ordered pipeline with extra bookkeeping. Including S4 makes the catalog's claim credible: two scenarios each way.

##### S5 — Hybrid: bounded blackboard as an orchestrator subroutine. Predicted winner: HYBRID.
Goal: a research-then-reconcile task that has *both* shapes. A top-level **Orchestrator** fans out S3-style independent research (its strength), then for each candidate plan invokes a **bounded blackboard subroutine** (S1-style reconciliation of the researched constraints, its strength). Gate: composite — outer gate `all findings present` AND inner gate `reconciled plan consistent`. **Real data:** S3 cassettes for the research leg + S1 CSV for the reconcile leg. Oracle: S3 citation-coverage AND S1 solver agreement. **Why hybrid wins:** neither pure topology is efficient across both legs; the hybrid routes at the top (cheap, parallel) and reacts within the team (cheap ripple). This is the first-class demonstration that the hybrid is a real engine (`ovb/hybrid.py`), not a talking point — it literally *calls* `blackboard.run(...)` as a subroutine with a `max_steps` budget passed down from the supervisor.

#### Engine-side changes (minimal, to keep fairness)

The two engines currently hardcode `task` and `build_agents`. I generalize both to take a `Scenario`:

```
def run(scenario: Scenario, llm, real=False, max_rounds/max_steps=...) -> RunResult
```

Nothing else in `orchestrator.py`/`blackboard.py` changes — `ORDER` becomes `scenario.order` (defaulting to roster order), `subs` is built from the same roster's `subscribes`, the gate becomes `scenario.is_consistent`. This is the *only* way to guarantee a new scenario can't secretly differ per engine: both call the identical `Scenario` methods.

#### The harness

`ovb/harness.py` runs the matrix `{scenario} × {engine} × {N runs}` and produces a `BenchResult` with per-run and aggregate stats. Key engineering:

**Real usage capture.** I extend `Usage` to the real Anthropic breakdown: `input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens` (verified fields; `total_input = input + cache_creation + cache_read`). `ClaudeLLM` reads all four from `msg.usage`; cost is computed with per-field pricing (cache reads are ~0.1×, cache writes ~1.25× base input) so the cost metric is *real*, not a token proxy. This matters for fairness: the orchestrator's fresh-context-per-call pattern gets **no** cache benefit, while the blackboard's shared context can be prompt-cached — reporting cache tokens exposes exactly that difference instead of hiding it.

**Determinism & reproducibility.** `temperature=0`, fixed `seed` where the API supports it, and a **cassette layer** (`ovb/cassette.py`): a record/replay wrapper around `ClaudeLLM` keyed by `sha256(model + system + prompt + max_tokens)` → recorded `(text, usage)`. `--record` hits the real API and writes `cassettes/<scenario>.jsonl`; default replay reads them, so CI and offline demos are byte-identical. Real LLMs are nondeterministic even at temp=0, so the cassette is what makes the *reported* numbers reproducible; the N-run variance below is what characterizes the *underlying* nondeterminism.

**Statistics.** For each (scenario, engine) I run N=20 (configurable) independent runs *without* the cassette (fresh API calls) to measure real variance, reporting per metric: mean, median, stdev, and a **bootstrap 95% CI** (10k resamples, stdlib `random` — no numpy dependency, matching the repo's stdlib-only ethos). The headline "blackboard wins" claim is only made when the CI of the *paired difference* (same run index, same cassette seed offset) excludes zero — I report the paired-difference bootstrap CI, not two overlapping marginal CIs, because the runs are naturally paired. Metrics per run: `n_calls`, `n_effective`, `n_wasted`, token totals (all 4 fields), real USD cost, wall-clock `latency_ms` (and critical-path latency for the parallel orchestrator, since fan-out latency ≠ sum of call latencies), `steps/rounds`, `ripple_depth` (S2), and `outcome ∈ {consistent, gate_timeout, oracle_fail}`.

**Outcome honesty.** A run that hits `max_steps`/`max_rounds` without passing the gate is `gate_timeout`, not counted as a win at any token cost. A run that passes the internal gate but fails the external `oracle` is `oracle_fail` — surfaced loudly, because it means the gate is a weaker proxy than we claimed (important for S2/S3 where the oracle is external truth).

**OTel alignment.** Each `Call` is emitted as a span with GenAI semantic-convention attributes (`gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`/`output_tokens`, `gen_ai.agent.name`) plus custom `ovb.engine`, `ovb.trigger`, `ovb.scenario`, `ovb.run_index`. This gives the viz slice a standard trace format and lets the repo export to any OTel backend without inventing a schema. Emission is behind an optional import so stdlib-only mode still works.

**Reporting.** `harness.py --report md|json|otel` prints a comparison table (per scenario: winner, paired-diff CI on tokens/cost/latency, outcome rates) and writes `output/bench.json` consumed by the viz slice for the dynamic dashboard. A `--matrix` run produces the full 5×3 grid that is the repo's flagship artifact.

#### Guarding the fairness trap, concretely

Three automated checks ship as tests (`tests/test_fairness.py`): (1) **roster identity** — assert the set of `Agent` objects and their `owns`/`subscribes` are byte-identical across what each engine receives for a scenario; (2) **gate identity** — assert both engines call the same `scenario.is_consistent` function object; (3) **policy symmetry** — a parametrized test that runs the orchestrator both with and without the gate early-exit and asserts the blackboard's reported win holds under the *stronger* (gate-checked) orchestrator. If any scenario can only make the blackboard win by denying the orchestrator the gate, that test fails and the scenario is disqualified from the "blackboard wins" list. This is the mechanical embodiment of principle #1.

#### Interfaces & contracts
##### Scenario protocol (`ovb/scenario.py`)
```python
from dataclasses import dataclass
from typing import Callable, Protocol

class Scenario(Protocol):
    name: str
    def initial_state(self) -> dict: ...
    def build_agents(self) -> list["Agent"]: ...          # roster; both engines get THIS
    def is_consistent(self, state: dict) -> bool: ...      # the shared gate
    def oracle(self, state: dict) -> bool: ...             # external ground truth
    @property
    def order(self) -> list[str]: ...                      # default = roster order
    def load_data(self) -> dict: ...                       # real CSV/repo/cassette inputs

#### Registry so the harness is data-driven, not hardcoded:
SCENARIOS: dict[str, Callable[[], Scenario]] = {
    "s1_reconcile": ..., "s2_debug": ..., "s3_research": ...,
    "s4_route": ..., "s5_hybrid": ...,
}
```

##### Generalized engines (only signature changes; bodies unchanged)
```python
#### ovb/orchestrator.py
def run(scenario: Scenario, llm, real=False, max_rounds=10,
        early_exit_gate=False) -> "RunResult": ...
#### ovb/blackboard.py
def run(scenario: Scenario, llm, real=False, max_steps=100) -> "RunResult": ...
#### ovb/hybrid.py  (NEW — first-class)
def run(scenario: Scenario, llm, real=False,
        inner_max_steps=50, outer_max_rounds=5) -> "RunResult":
    # supervisor fans out research (orchestrator-style, asyncio.gather),
    # then for each candidate calls blackboard.run(inner_scenario, llm,
    # max_steps=inner_max_steps) as a bounded subroutine.
```

##### Extended Usage / real Anthropic fields (`ovb/llm.py`)
```python
@dataclass
class Usage:
    input_tokens: int = 0            # non-cached input
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    @property
    def total_input(self) -> int:
        return (self.input_tokens + self.cache_creation_input_tokens
                + self.cache_read_input_tokens)
    @property
    def total(self) -> int: return self.total_input + self.output_tokens

#### ClaudeLLM.complete reads (verified live API fields):
####   u = msg.usage
####   Usage(u.input_tokens, u.output_tokens,
####         u.cache_creation_input_tokens, u.cache_read_input_tokens)

#### Pricing (real cost, per 1e6 tokens; injected, not hardcoded):
@dataclass
class Price: in_: float; out: float; cache_write: float; cache_read: float
def usd(u: Usage, p: Price) -> float:
    return (u.input_tokens*p.in_ + u.output_tokens*p.out
            + u.cache_creation_input_tokens*p.cache_write
            + u.cache_read_input_tokens*p.cache_read) / 1e6
```

##### Cassette record/replay (`ovb/cassette.py`)
```python
class Cassette:
    def __init__(self, path: str, mode: str): ...  # "record" | "replay"
    def _key(self, model, system, prompt, max_tokens) -> str:  # sha256 hex
        ...
class CassetteLLM:                # wraps ClaudeLLM or replays
    def complete(self, system, prompt, expect="") -> Completion: ...
#### on-disk line schema (cassettes/<scenario>.jsonl):
#### {"key": "<sha256>", "text": "...",
####  "usage": {"input_tokens":.., "output_tokens":..,
####            "cache_creation_input_tokens":.., "cache_read_input_tokens":..}}
```

##### Harness result schemas (`ovb/harness.py`)
```python
@dataclass
class RunResult:
    scenario: str; engine: str; run_index: int
    consistent: bool; outcome: str        # consistent|gate_timeout|oracle_fail
    oracle_pass: bool
    n_calls: int; n_effective: int; n_wasted: int
    usage: Usage; usd: float
    latency_ms: float; critical_path_ms: float
    steps: int; ripple_depth: int
    recorder: "Recorder"                  # WORM events + per-call spans

@dataclass
class Aggregate:                          # per (scenario, engine)
    metric: str; mean: float; median: float; stdev: float
    ci95: tuple[float, float]             # bootstrap, 10k resamples

@dataclass
class PairedDiff:                         # per (scenario, metric)
    winner: str                           # "blackboard"|"orchestrator"|"tie"
    mean_diff: float; ci95: tuple[float, float]  # excludes 0 => significant

def bootstrap_ci(xs: list[float], iters=10_000, alpha=0.05
                 ) -> tuple[float, float]: ...      # stdlib random only
def run_matrix(scenarios: list[str], engines: list[str], n: int,
               real: bool, cassette: str|None) -> "BenchResult": ...
```

##### OTel GenAI span (per Call; `ovb/otel.py`, optional import)
```
span name: "chat {model}"
attrs: gen_ai.operation.name=chat, gen_ai.request.model=<model>,
       gen_ai.request.temperature=0,
       gen_ai.usage.input_tokens=<u.total_input>,
       gen_ai.usage.output_tokens=<u.output_tokens>,
       gen_ai.agent.name=<agent>,
       ovb.engine, ovb.scenario, ovb.run_index, ovb.trigger,
       ovb.cache_read_input_tokens, ovb.cache_creation_input_tokens
```

##### File layout added by this slice
```
ovb/scenario.py  ovb/hybrid.py  ovb/cassette.py  ovb/harness.py  ovb/otel.py
ovb/scenarios/{s1_reconcile,s2_debug,s3_research,s4_route,s5_hybrid}.py
data/s1_estimates.csv  data/s1_solver.py  data/s2_repo/  data/s4_tickets.csv
cassettes/{s1..s5}.jsonl
tests/test_fairness.py  tests/test_scenarios.py
demos/run_matrix.py
```

#### Key decisions
- **Introduce a `Scenario` protocol and generalize both engines to `run(scenario, llm, ...)` instead of adding per-scenario engine code.** — It is the only structural guarantee that a scenario cannot secretly differ across engines — both call the identical Scenario methods for agents/gate/order. Fairness becomes a property of the type system, not of reviewer vigilance. _(alt: Copy-paste engine variants per scenario (invites divergence); or a config dict (weaker typing, easy to smuggle per-engine keys).)_
- **Ship an `--orch-early-exit` flag and always report both orchestrator variants; only claim a blackboard win when it survives the gate-checked orchestrator.** — Directly defuses the fairness trap: early-exit is a one-line policy, not topology. If the blackboard only wins because the orchestrator lacks the gate, that is not a topology win and must not be reported as one. _(alt: Give only the blackboard the gate (dishonest); or never let the orchestrator early-exit (understates orchestrator, also dishonest).)_
- **Include TWO scenarios where the orchestrator rightly wins (S3 research fan-out, S4 routing) alongside two blackboard-favoring ones (S1, S2) and one hybrid (S5).** — A catalog that only ever favors the blackboard would be rigged. Balanced outcomes are what make the 'when to use which' claims credible to senior architects. _(alt: A blackboard-showcase catalog (loses credibility); a single knob-turned task (doesn't generalize the insight).)_
- **Extend `Usage` to the real 4-field Anthropic breakdown and compute real USD with per-field pricing including cache read/write rates.** — Cost is a first-class metric and the orchestrator's fresh-context-per-call vs blackboard's cacheable shared context is a REAL economic difference. Reporting cache tokens exposes it instead of hiding it behind a flat token proxy. Fields verified against current Anthropic API. _(alt: Keep 2-field prompt/completion tokens (hides caching economics, understates the orchestrator's true cost disadvantage or advantage).)_
- **Cassette record/replay keyed by sha256(model+system+prompt+max_tokens) for reproducibility, but run variance/CIs from fresh (non-cassette) API calls.** — Cassettes make the demo offline/deterministic/byte-identical; but real LLMs are nondeterministic even at temp=0, so the variance and CIs that back statistical claims must come from fresh runs. Conflating the two would report fake zero-variance. _(alt: Only cassettes (fake determinism, no honest variance); only live (non-reproducible demos, needs keys, flaky CI).)_
- **Report paired-difference bootstrap CIs (same run index across engines) rather than two marginal CIs.** — Runs are naturally paired (same seed offset, same scenario); paired differencing removes between-run noise and gives a tighter, correct significance test. Overlapping marginal CIs would understate significance. _(alt: Two independent CIs and eyeball overlap (statistically weaker, can miss real effects).)_
- **Make S2 (code-debug) and S3 (research) carry the security and honesty caveats operationally: an injected-input variant for S2 and an oracle_fail outcome path everywhere.** — Principle #4 (honest) demands the injection blast-radius and 'gate is a proxy' caveats be demonstrated in running code, not just prose. The shared board's injection amplification is a measurable property, and oracle_fail surfaces when the internal gate diverges from external truth. _(alt: Discuss security only in docs (unconvincing to expert audience); trust the gate as ground truth (hides the proxy risk).)_

#### Risks
- **S2 (code-debug) and S3 (research) are inherently nondeterministic; even temp=0 real runs vary in patch content, so a run may pass the internal gate but the oracle can flap between runs.** → Separate the gate (internal, deterministic given a state) from the oracle (external truth); report oracle_pass rate over N runs with a CI rather than a single boolean. Freeze the S2 repo at a pinned commit and vendor it offline so only the LLM varies, not the environment.
- **The blackboard's win in S1/S2 could be an artifact of subscription topology I chose, effectively encoding an early-exit as a subscription edge.** → test_fairness.py asserts subscription edges are derived only from real data-dependencies in the state schema (Budget writes max_scope which Scope reads), and runs the orchestrator WITH the gate; the win must hold against the stronger orchestrator or the scenario is disqualified.
- **Real Anthropic cache behavior is opportunistic and TTL-bound; cache_read tokens may be zero in short runs, making the cost-difference story collapse and looking like a bug.** → Explicitly set cache_control breakpoints on the shared system/role prompts, warm the cache in a preflight call, and report cache hit rate as a metric so a zero is visibly explained rather than mistaken for an error; document the 5m/1h TTL dependence.
- **Parallel orchestrator fan-out (S3/S5) makes summed call latency misleading vs blackboard's serial latency, unfairly flattering one side.** → Record both total_latency_ms (sum) and critical_path_ms (max over concurrent calls via asyncio) and headline the critical path for parallel legs; the viz slice shows both so the reader can't be misled.
- **Bootstrap CIs on N=20 with heavy-tailed latency can be unstable, over/under-stating significance.** → Use the paired-difference bootstrap (removes between-run variance), report token/cost significance (low variance, the real claim) separately from latency (high variance, reported with wider CI and a caveat), and make N configurable up to 100 for the flagship matrix run.

#### Open questions
- Which specific public datasets/repos to pin: candidate IT-estimation CSV for S1, a small pure-Python OSS utility with a reproducible buggy commit for S2, and a public support-ticket CSV for S4 — need license check (prefer MIT/CC0/public-domain) before vendoring.
- Should S3/S5 use the real Anthropic web-search/tool-use API surface or the harness's own WebSearch/WebFetch tools at record time? The former is more 'real Anthropic' but couples the scenario to a beta tool API; leaning toward capturing tool results into cassettes either way.
- N for the flagship matrix: 20 is enough for token/cost significance but latency CIs may need 50–100; trade wall-clock/API-cost of recording against CI tightness — needs a budget decision from the orchestration owner.
- Whether to gate the 'blackboard wins' headline on the paired-diff CI excluding zero for tokens AND cost, or tokens alone (cost can flip sign under caching) — I lean tokens-primary, cost-reported-with-caveat, but this is a reporting-policy call to align with the docs slice.
- How to attribute the hybrid's (S5) cost between its orchestrator and blackboard legs in the dashboard so the viz slice can render a stacked breakdown — needs a shared field convention (ovb.leg = outer|inner) agreed with the viz slice.

### 10.6 Guardrails, Security & When-To-Use: the opinionated guidance layer for OVB

_A concrete guardrails/security/decision layer for the ovb repo: a reusable `ovb/guardrails.py` (schema-validated writes, iteration caps + circuit breakers, deterministic gate assertion, retry/idempotency, HITL interrupt/resume via checkpoints, cost governor with real Anthropic cache-token accounting), an `ovb/security.py` blast-radius harness (provenance/trust tags on board entries, write validation, quarantine + re-trigger caps, a `PoisonAgent` that empirically demonstrates orchestrator containment vs blackboard amplification), and a machine-readable `docs/decision.yaml` + `ovb/advisor.py` that drives both a CLI and the UI's "which should I use?" helper. Everything is wired to the existing kernel with only additive changes, preserving the fairness invariant (only the control model differs) and honesty invariants ("LLM never renders the verdict", start single-agent, reasoning-models-substitute-for-fan-out)._

#### Scope and design stance

The seed already proves the *performance* story (blackboard 7 calls/511 tok vs orchestrator 12/908). My slice makes the repo *safe to ship and easy to decide*. Three deliverables, all additive to the existing kernel: `ovb/guardrails.py` (production guardrails), `ovb/security.py` (blast-radius harness), and `ovb/advisor.py` + `docs/decision.yaml` (machine-readable when-to-use). A cross-cutting rule governs every line: **guardrails are shared substrate, not per-engine.** A guardrail that lives in only one engine would silently re-credit the topology, breaking the fairness invariant. So guardrails wrap `agent.act` and the write path *identically* in both `orchestrator.run` and `blackboard.run`; the only place they legitimately differ is the security harness, because differing blast radius *is* the finding.

#### 1. Guardrails as a shared, composable middleware (`ovb/guardrails.py`)

The current engines call `agent.act(view, llm)` then loop `for k,v in patch.items(): rec.record_write(...); state[k]=v`. I insert a single seam — a `GuardedWriter` and an `act` wrapper — so both engines gain identical protection with a two-line diff each.

**Schema-validated writes.** The strongest honesty guarantee in this repo is "the LLM never renders the final verdict" — `is_consistent()` is code. I extend that principle to *every write*, not just termination. Each field gets a `FieldSpec(type, domain, owner)`; a write is rejected unless (a) the writing agent `owns` the field (already implied by `Agent.owns`, now *enforced*), (b) the value satisfies the spec's type and domain predicate. In real mode the model narrates and the rule computes the number, but a corrupted rule or a future tool-using agent still cannot post `scope = -999` or `risk = "ship it"`. Rejection is a first-class event (`ValidationReject` on the WORM log), not an exception that aborts the run — this is what makes injection *observable* rather than merely blocked. Signature: `validate_write(agent_name, field, value, specs) -> Ok | Reject(reason)`.

**Iteration caps + circuit breakers.** `max_steps`/`max_rounds` already cap *total* work. That is necessary but blunt: it can't tell "converging slowly" from "two agents flip-flopping forever." I add a `CircuitBreaker` with three independent trips, checked in the write loop: (1) **oscillation** — a `(field, old→new)` transition seen ≥ K times (default 3) means a cycle, trip; (2) **no-progress** — steps since the last *effective* write exceeds a budget, trip; (3) **fan-out storm** — writes-per-step exceeds a threshold (the security signal, see §2). A trip records a `BreakerTrip` event and ends the run in a `halted` (not `consistent`) terminal state, so the report distinguishes "converged" from "stopped by a breaker." Crucially the breaker is engine-agnostic: it observes the write stream, which both engines produce.

**Retry + idempotency.** Real API calls fail (429, 529 overloaded, network). `with_retry(fn, policy)` wraps `llm.complete` with exponential backoff + full jitter, honoring `Retry-After`, retrying only idempotent-safe status classes. Idempotency is free here and worth stating as a pattern: `agent.act` is a *pure function of the view* (the rule is deterministic; the narration is cosmetic), so a retried call after a mid-write crash is safe — re-deriving the patch from the current state yields the same patch. I make this explicit with an `idempotency_key = hash(agent, canonical(view))`; a `ReplayCache` short-circuits duplicate keys within a run, which also underpins the cassette layer another slice owns. The deep point for architects: **idempotency is trivial in this design precisely because writes are last-writer-wins on typed fields, not append-to-a-log-of-instructions.** Systems whose "memory" is free-text accumulate un-revertable side effects; ours don't.

**HITL interrupt/resume.** The bounded blackboard's control unit is the natural interrupt point. I add checkpoint/resume: `Checkpoint(state, queue, seq, breaker_counts)` is serializable to JSON. An `InterruptPolicy` fires on a predicate over a *proposed* write (e.g. `field == "budget_k" and value > cap`, or trust below a threshold) and, instead of applying, raises `Interrupt(checkpoint, pending_write)`. The engine returns control to the caller with a resumable token. `resume(checkpoint, decision)` re-enters the loop with the human's `approve|reject|edit` decision applied as the next write. This is implemented once and shared: the orchestrator interrupts *between agents in a sweep*, the blackboard *between queue pops* — same `Checkpoint` shape, so a UI "step / pause / approve" control works identically over both. I deliberately make the interrupt synchronous and checkpoint-based rather than a callback, because callbacks don't survive a process restart and can't drive a stateless SSE UI; a serialized checkpoint can.

**Cost governor.** The seed sums `Usage(prompt_tokens, completion_tokens)`. Real Anthropic responses carry four token classes — `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens` — priced differently (cache *reads* ~0.1×, cache *writes* ~1.25× base input). I extend `Usage` with the two cache fields (defaulting 0 so mock math is unchanged) and add a `Price` table keyed by model. The governor enforces a per-run **token budget** and **USD budget** as a fourth breaker: before each call, `governor.check(projected)`; on trip, halt with `budget_exceeded`. Two correctness traps I encode because they bite everyone: (1) **streaming usage is cumulative** — `message_delta` repeats `message_start`'s cache counts as running totals, so naïvely summing per-event double-counts; `ClaudeLLM` must read final usage once, or diff cumulatively, never add both events (this is a live bug class in LangChain/cline as of 2026). (2) **cache reads still count as input for rate limits** even though they're ~free in dollars, so latency/throughput governance and cost governance use different denominators. The governor exposes both `dollars()` and `rate_limited_input_tokens()`.

#### 2. Blast radius: the security centerpiece (`ovb/security.py`)

This is where topology stops being a performance question and becomes a *containment* question, and where the repo earns its "honest" claim. The thesis, made empirical: **on a shared blackboard, one poisoned write re-triggers every subscriber of the touched field — injection *amplifies* along the subscription graph; under message-passing orchestration, a poisoned agent's output is re-read only on the next fixed sweep and reaches only agents that consume that field — blast radius is bounded by the hand-off graph, not the subscription graph.**

I demonstrate it, not assert it. A `PoisonAgent` (a normal `Agent` whose rule, when a `trust` gate is off, writes an out-of-domain value plus attempts to write a field it doesn't own) is injected into the *same roster* for both engines. Then `security.py` runs both engines and reports, from the WORM log, the **amplification factor** = (agent-invocations causally downstream of the poisoned write) / (poisoned writes). Because the subscription graph fans `scope → {Budget, Timeline, Risk}`, a poisoned `scope` on the board wakes three agents *immediately and recursively*; the orchestrator absorbs it into at most one extra sweep. The number falls out of control logic exactly like the token number does — nothing hardcoded.

**Mitigations, implemented and measured (defense-in-depth, ordered by leverage):**

1. **Write validation (schema + ownership)** — from §1. This alone neutralizes the *malformed* class: `scope = -999` and the cross-field write are rejected at the boundary. Blast radius of a *rejected* write is zero (no state change ⇒ no ripple). This is the single highest-leverage control and the reason validation lives in the shared path.
2. **Provenance + trust tags on board entries.** Every WORM `Event` gains `provenance: {agent, trust: float, derived_from: [event_seq...]}`. Trust is assigned at the source: external/seed inputs and tool-fetched data start at a configured `untrusted` level; agent-derived writes inherit `min(parents.trust)` (a lattice meet — corruption can't launder itself clean by passing through a trusted agent). This is the LLM-tagging / origin-bound-authority pattern from the 2026 literature, made concrete as a monotone label that survives propagation.
3. **Trust-gated re-trigger (quarantine).** The blackboard's `enqueue` is wrapped: a write whose provenance trust is below `retrigger_threshold` is applied to state but **does not wake subscribers** — it is *quarantined*, logged, and (in HITL mode) raises an `Interrupt`. This is the direct structural fix for amplification: it severs the poisoned write from the subscription cascade while preserving auditability. Measured effect: amplification factor collapses toward the orchestrator's.
4. **Quarantine re-trigger cap.** Even trusted cascades can storm; the fan-out breaker (§1) caps *how many* re-triggers a single write may spawn, converting an unbounded cascade into a bounded, logged one.

The honest coda: message-passing's containment is **not free** — it's the same isolation that costs the orchestrator its whole-roster re-sweeps. So the security win and the performance loss are *the same property viewed twice*. I state this explicitly in `docs/SECURITY.md` so no reader concludes "blackboard bad." The correct reading: **use the bounded blackboard for interdependence, but if inputs are untrusted, pay for trust tags + quarantine; if you can't, prefer message-passing and eat the token cost.** That trade is the decision framework's untrusted-input branch.

#### 3. When-to-use as executable policy (`docs/decision.yaml` + `ovb/advisor.py`)

The seed's WHEN-TO-USE.md is prose. To *drive a UI helper* it must be data. I add `docs/decision.yaml`: a typed questionnaire (nodes with `id`, `question`, `answers→next|verdict`, `weight`) encoding the decision tree — single-agent vs orchestrator vs blackboard vs hybrid — plus a `security_overlay` that can *downgrade* a blackboard verdict to "blackboard + trust-tags" or "prefer message-passing" when the untrusted-input flag is set. `advisor.py` loads it, runs an interactive CLI (`python -m ovb.advisor`) and exposes `advise(answers: dict) -> Verdict` consumed by the web UI's `/api/advise` endpoint. Keeping the tree in YAML means the prose doc, the CLI, and the UI cannot drift — they share one source. The tree's root is deliberately the counterweight ("Is one agent with a big thinking budget enough? → start there"), so the default answer is *not* "build multi-agent," honoring the "don't build multi-agents" and reasoning-models-substitute-for-fan-out principles as the literal first gate.

#### Concurrency note

Guardrails are synchronous in the reference path (the engines are sequential loops), but the `CircuitBreaker`, `Governor`, and `TrustLedger` are designed as thread-safe accumulators (single lock, or per-agent shards reduced at barrier) so a future async orchestrator that fans agents out with `asyncio.gather` can share them without a redesign. The interrupt/resume checkpoint is the async story's backbone: an async engine `await`s a human decision by persisting the checkpoint and returning, exactly as the sync one does.

#### What I deliberately do *not* build

No auth, no network policy engine, no real secrets management — those are deployment concerns and would bloat a reference repo. I stop at the boundary where the *pattern* is demonstrated: validation, provenance, quarantine, caps, governance, HITL. Each is <60 lines and testable in mock mode.

#### Interfaces & contracts
##### `ovb/guardrails.py`

```python
#### --- schema-validated writes -------------------------------------------------
@dataclass(frozen=True)
class FieldSpec:
    type: type
    domain: Callable[[Any], bool]      # predicate; e.g. lambda v: 0 <= v <= 8
    owner: str                          # agent name allowed to write this field

SPECS: dict[str, FieldSpec] = {
    "scope":          FieldSpec(int, lambda v: 0 <= v <= 8, "Scope"),
    "max_scope":      FieldSpec(int, lambda v: 0 <= v <= 8, "Budget"),
    "budget_k":       FieldSpec(int, lambda v: 0 <= v <= 1000, "Budget"),
    "timeline_weeks": FieldSpec(int, lambda v: 0 <= v <= 60, "Timeline"),
    "risk":           FieldSpec(str, lambda v: v in {"low","medium","high"}, "Risk"),
}

@dataclass
class Reject: field: str; value: Any; reason: str            # "domain"|"ownership"|"type"
Ok = None
def validate_write(agent: str, field: str, value: Any,
                   specs=SPECS) -> Reject | None: ...

#### --- circuit breaker (engine-agnostic; observes the write stream) ------------
@dataclass
class BreakerConfig:
    max_steps: int = 100
    oscillation_k: int = 3          # same (field,old->new) seen K times => trip
    no_progress_budget: int = 8     # steps since last effective write
    fanout_max: int = 6             # writes spawned by one call (storm)

class CircuitBreaker:
    def __init__(self, cfg: BreakerConfig): ...
    def observe(self, step: int, writes: dict, transitions: list) -> str | None:
        # returns None to continue, or a trip reason:
        # "steps"|"oscillation"|"no_progress"|"fanout"|"budget"
        ...

#### --- retry / idempotency -----------------------------------------------------
@dataclass
class RetryPolicy: max_attempts:int=4; base_ms:int=500; retry_on=(429,529,503)
def with_retry(fn: Callable[[], T], policy: RetryPolicy) -> T: ...   # jittered backoff
def idempotency_key(agent: str, view: dict) -> str:                  # sha256 of canonical view
    ...

#### --- cost governor (real Anthropic cache-token accounting) -------------------
@dataclass
class Price:                        # USD per 1M tokens, per model
    input: float; output: float; cache_write: float; cache_read: float
PRICES = {"claude-sonnet-5": Price(3.0, 15.0, 3.75, 0.30)}   # illustrative

@dataclass
class Governor:
    price: Price
    usd_cap: float | None = None
    token_cap: int | None = None
    def check(self, projected: "Usage") -> str | None: ...   # None | "budget"
    def dollars(self, u: "Usage") -> float: ...
    def rate_limited_input_tokens(self, u: "Usage") -> int:  # input + cache_read + cache_write
        ...

#### --- HITL interrupt / resume -------------------------------------------------
@dataclass
class Checkpoint:                   # JSON-serializable
    engine: str; state: dict; queue: list; seq: int; breaker: dict
@dataclass
class Interrupt(Exception):
    checkpoint: Checkpoint; pending: tuple   # (agent, field, value, provenance)
class InterruptPolicy:
    def should_interrupt(self, agent: str, field: str, value: Any,
                         prov: "Provenance") -> bool: ...
def resume(checkpoint: Checkpoint, decision: str,           # "approve"|"reject"|"edit"
           edit: dict | None, llm, **guards) -> dict: ...   # re-enters the engine loop
```

##### `ovb/llm.py` — additive `Usage` fields (backward compatible)

```python
@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_creation_tokens: int = 0   # NEW, default 0 -> mock math unchanged
    cache_read_tokens: int = 0       # NEW
    # ClaudeLLM.complete now reads all four; on streaming, take FINAL usage only
    # (message_delta repeats message_start cache counts cumulatively — do NOT sum both)
```

##### `ovb/security.py`

```python
@dataclass
class Provenance:
    agent: str
    trust: float                     # 0.0 untrusted .. 1.0 fully trusted
    derived_from: list[int]          # parent Event seqs; child trust = min(parents)
UNTRUSTED, TRUSTED = 0.0, 1.0

def make_poison_agent(target_field="scope", bad_value=-999) -> "Agent": ...
    # rule attempts (a) out-of-domain write to owned field and
    # (b) a write to a field it does NOT own -> both must be rejected by validation

@dataclass
class BlastReport:
    engine: str
    poisoned_writes: int
    downstream_invocations: int
    amplification: float             # downstream / poisoned  (emergent, not hardcoded)
    rejected_writes: int
    quarantined_writes: int

def run_blast(engine: str, *, mitigations: set[str]) -> BlastReport: ...
    # mitigations subset of {"validation","provenance","quarantine","fanout_cap"}

#### quarantine hook wrapping blackboard.enqueue:
def gated_enqueue(enqueue, prov: Provenance, threshold: float,
                  breaker: "CircuitBreaker") -> Callable: ...
    # if prov.trust < threshold: apply write but DO NOT wake subscribers; log + (HITL) Interrupt
```

##### `docs/decision.yaml` (drives CLI + UI `/api/advise`)

```yaml
version: 1
root: q_single
nodes:
  q_single:
    question: "Can one agent with a large thinking budget do this acceptably?"
    answers: {yes: {verdict: single_agent}, no: {next: q_interdep}}
  q_interdep:
    question: "Do sub-results depend on each other mid-run?"
    answers: {no: {next: q_parallel}, yes: {next: q_immediate}}
  q_parallel:
    question: "Independent parallel fan-out (search / N summaries)?"
    answers: {yes: {verdict: orchestrator}, no: {verdict: orchestrator}}
  q_immediate:
    question: "Must one agent's write immediately re-open another's, before the end?"
    answers: {no: {verdict: orchestrator}, yes: {next: q_bounded}}
  q_bounded:
    question: "Need deterministic stop + write-level audit?"
    answers: {yes: {verdict: blackboard_bounded}, no: {verdict: blackboard_bounded}}
security_overlay:            # applied AFTER a verdict when untrusted_inputs=true
  blackboard_bounded: blackboard_bounded_trusttagged   # +provenance +quarantine
  # if trust tagging is infeasible -> advisor recommends orchestrator (containment)
verdicts:
  single_agent: {label: "Single agent", why: "No interdependence/parallelism; start here."}
  orchestrator: {label: "Orchestrator", why: "Tree-shaped or untrusted inputs; blast radius bounded by hand-off graph."}
  blackboard_bounded: {label: "Bounded blackboard", why: "Interdependent + immediate ripple; gate + control unit + caps."}
  hybrid: {label: "Hybrid (orchestrator of bounded blackboards)", why: "Route at top, react within a trusted sub-team."}
```

##### `ovb/advisor.py`

```python
@dataclass
class Verdict: id: str; label: str; why: str; overlay: str | None = None
def load_tree(path="docs/decision.yaml") -> dict: ...
def advise(answers: dict[str, str], *, untrusted_inputs: bool = False,
           tree=None) -> Verdict: ...          # pure; used by UI /api/advise
def main() -> None: ...                          # interactive CLI: python -m ovb.advisor
```

##### Engine integration (the two-line seam — fairness preserved)

```python
#### in BOTH orchestrator.run and blackboard.run, replacing the raw write loop:
for k, v in patch.items():
    prov = trust_ledger.derive(name, view, k)                     # provenance
    if (rej := validate_write(name, k, v)) is not None:           # schema+ownership
        rec.record_reject(name, rej); continue
    if policy and policy.should_interrupt(name, k, v, prov):      # HITL
        raise Interrupt(checkpoint_now(), (name, k, v, prov))
    rec.record_write(name, k, state.get(k), v, prov)
    state[k] = v
    enqueue_fn(subs.get(k, []), prov)   # blackboard: gated by trust; orch: no-op
if (reason := breaker.observe(step, patch, transitions)):         # circuit breaker
    return terminate(state, rec, status=reason)
```

##### Files added / touched
- add: `ovb/guardrails.py`, `ovb/security.py`, `ovb/advisor.py`, `docs/decision.yaml`, `docs/SECURITY.md`, `docs/GUARDRAILS.md`, `demos/run_blast.py`, `tests/test_guardrails.py`, `tests/test_security.py`, `tests/test_advisor.py`
- touch (additive only): `ovb/llm.py` (Usage +2 fields), `ovb/instrumentation.py` (Event.provenance, record_reject, BreakerTrip), `ovb/orchestrator.py` & `ovb/blackboard.py` (the shared write-seam above), `docs/WHEN-TO-USE.md` (link to decision.yaml)

#### Key decisions
- **Guardrails live in a shared module wrapping the identical write-seam in both engines; only the security blast-radius harness is allowed to differ per engine.** — The fairness invariant says only the control model may differ. A guardrail present in one engine would silently re-credit the topology. The one exception (blast radius) is legitimate because differing containment IS the measured finding. _(alt: Per-engine guardrails (rejected: breaks fairness); a decorator framework (rejected: over-engineered for ~40-line engines).)_
- **Extend the 'LLM never renders the verdict' principle from termination to EVERY write via schema+ownership validation, with rejects logged as WORM events rather than raised.** — Makes injection observable, not just blocked; a rejected write causes zero state change and therefore zero ripple, which is the single highest-leverage blast-radius control. _(alt: Validate only at the gate (rejected: too late, poisoned intermediate writes already rippled); raise on reject (rejected: loses the audit signal and aborts otherwise-recoverable runs).)_
- **Demonstrate blast-radius amplification empirically with an injected PoisonAgent and an amplification factor computed from the WORM log, not asserted in prose.** — Consistency with the repo's 'numbers emerge from control logic, nothing hardcoded' ethos; a measured factor is more persuasive and lets the UI show it live. _(alt: Prose-only security section (rejected: unfalsifiable, off-brand for a measurement repo).)_
- **Trust is a monotone lattice-meet label: child trust = min(parent trusts); low-trust writes are quarantined (applied but do not wake subscribers).** — Prevents corruption from laundering itself clean by passing through a trusted agent; quarantine severs the exact edge (write->re-trigger) that causes amplification while preserving auditability. Matches 2026 origin-bound-authority / LLM-tagging literature. _(alt: Binary trusted/untrusted (rejected: no propagation semantics); dropping low-trust writes entirely (rejected: destroys audit trail and can deadlock the gate).)_
- **Encode the when-to-use tree as machine-readable docs/decision.yaml consumed by both the CLI advisor and the UI, with the root gate being the 'is one agent enough?' counterweight.** — Single source of truth prevents drift between prose, CLI, and UI; making 'start single-agent' the literal first node bakes the honest counterargument into the default path. _(alt: Duplicate logic in prose + UI code (rejected: guaranteed drift); hardcode the tree in Python (rejected: not shareable with a JS UI without a second copy).)_
- **Add cache_creation/cache_read token fields to Usage and a Governor that reports dollars() and rate_limited_input_tokens() separately, reading only FINAL streaming usage.** — Real Anthropic cost has four token classes priced very differently; cache reads are ~free in USD but still count against rate limits, so cost and throughput governance need different denominators. Streaming message_delta repeats cache counts cumulatively — summing both events double-counts (a live 2026 bug class). _(alt: Keep the 2-field Usage (rejected: can't model real cost/caching, violates the REAL principle); a single blended cost number (rejected: hides the rate-limit vs dollars distinction).)_
- **HITL is checkpoint/resume with a JSON-serializable Checkpoint, not a callback.** — Checkpoints survive process restarts and drive a stateless SSE/HTTP UI; the same Checkpoint shape works for orchestrator (between agents) and blackboard (between pops) and is the backbone for a future async engine. _(alt: In-process callbacks (rejected: don't survive restart, can't be driven by a stateless web UI).)_

#### Risks
- **Adding guardrails could inadvertently change the headline benchmark numbers (7/511 vs 12/908), making reviewers think the comparison was rigged.** → Guardrails are no-ops on the clean task (all writes valid, all trust=1.0, no breaker trips), so mock benchmark numbers are byte-identical with guardrails on. tests/test_smoke.py asserts the unchanged numbers with guardrails enabled; the security harness runs only on the poisoned roster.
- **Quarantine (not waking subscribers on low-trust writes) could prevent the deterministic gate from ever being satisfied, causing a false 'halted' where a real system would converge.** → Quarantine still applies the write to state (only the re-trigger is severed) and raises an Interrupt in HITL mode so a human can approve propagation; the breaker's no_progress trip guarantees termination either way, and the report labels it 'halted-quarantine' distinctly from 'converged'.
- **The trust-meet propagation could be gamed if an agent derives a write without declaring derived_from, inheriting default-high trust.** → derived_from is computed by the shared TrustLedger from the agent's declared subscribes/owns and the current view's provenance, not self-reported by the agent; an undeclared dependency simply can't raise trust above its inputs' meet.
- **Illustrative PRICES table drifts from real Anthropic pricing and misleads architects on absolute cost.** → Mark PRICES as illustrative-and-configurable in code and docs, load overrides from env/JSON, and frame all cost claims as ratios (orchestrator vs blackboard) which are pricing-independent; never publish an absolute dollar figure as fact.
- **Streaming cache-token accounting is subtle; a wrong implementation would double-count and undercut the 'real cost' claim.** → ClaudeLLM reads usage from the final message object (non-streaming path) by default; the streaming path has an explicit test that asserts cache_read+cache_write <= input_tokens (the impossibility check) to catch double-counting in CI.

#### Open questions
- Should the security_overlay ever recommend the HYBRID verdict (orchestrator routing to trusted bounded-blackboard sub-teams) automatically when untrusted_inputs is set, or leave hybrid as an explicit user opt-in? Auto-recommending is powerful but risks over-selling the most complex topology.
- What default trust threshold and fanout_max make the amplification contrast pedagogically clear without looking hand-tuned? These are demo parameters that must be defensible as 'reasonable defaults,' not cherry-picked to inflate the gap.
- Should HITL interrupt/resume be exercised in the offline cassette layer (record a human decision alongside the LLM cassette) so the UI's approve/reject flow is demoable without a live operator? This couples my slice to the record/replay slice's schema.
- Do we want a fourth 'group-chat/debate' branch in decision.yaml now (RESEARCH already names it as a distinct topology) or defer until an engine implements it, to avoid advising a topology the repo can't demonstrate?

### 10.7 ovb Repo Engineering & DX: clone-and-run in <5 min, cassette-first, one-env-var to real

_Evolve the `ovb` seed into a src-layout, uv-managed package with a typer CLI, pydantic-settings config, a versioned record/replay cassette layer that makes the ClaudeLLM path exercisable offline and reproducibly, a FastAPI+SSE web backend launched via the CLI, a pytest suite (smoke + Hypothesis gate-convergence property tests + a golden-cassette test that BOTH engines reach the identical gate), GitHub Actions CI (ruff+mypy+pytest+a cassette-replay UI-backend smoke), an mkdocs-material docs site, and a plugin-registration model so new scenarios/agents/engines drop in without touching the kernel. The load-bearing new subsystem is the cassette layer: a content-addressed request key over (model, temperature, system, messages, max_tokens) → a recorded Anthropic response including the full usage block, so fairness (temp=0 + N runs + variance) and offline determinism are both real, not mocked._

#### Design goals and the one hard constraint

The DX contract is: `git clone && uv sync && uv run ovb bench` prints the comparison and writes `output/report.html` in well under five minutes, on a laptop, with **no API key and no network**. Opting into real calls is exactly one env var (`OVB_LLM__MODE=real` plus `ANTHROPIC_API_KEY`). Everything else — src layout, config, CLI, web, tests, CI, docs, plugins — serves that contract and the project's fairness principle.

The single most important engineering decision: **cassettes wrap `ClaudeLLM`, not `MockLLM`.** `MockLLM` stays as the zero-dependency, zero-artifact fallback (it must keep working with a fresh checkout that has no cassettes). But the *default demo path* replays a recorded real Claude interaction. That means the offline demo shows genuine token/latency/cache numbers from the API, the fairness machinery (temp=0, N runs, variance) is exercised against real response shapes, and "mock mode" is demoted to a smoke-only escape hatch. This resolves the tension between REAL and reproducible without cheating.

#### Final directory layout (evolving `ovb`, src layout)

```
ovb/                                repo root
  pyproject.toml                    uv-managed, src layout, PEP 621, dep groups
  uv.lock                           committed — reproducibility guarantee
  Makefile  justfile                thin wrappers over `uv run ovb ...`
  .env.example  .python-version     3.13 pinned
  mkdocs.yml  CONTRIBUTING.md  SECURITY.md  LICENSE  README.md
  .github/workflows/ci.yml
  src/ovb/
    __init__.py                     __version__, public re-exports
    config.py                       pydantic-settings Settings (NEW)
    cli.py                          typer app (NEW)
    llm.py                          MockLLM, ClaudeLLM (+ streaming usage), CassetteLLM (EVOLVED)
    cassette.py                     record/replay store, request keying (NEW)
    agents.py  task.py              kernel — unchanged semantics
    instrumentation.py              Recorder + WORM + OTel export hook (EVOLVED)
    engines/
      __init__.py                   Engine protocol + registry
      orchestrator.py  blackboard.py  hybrid.py   (hybrid = bounded blackboard as subroutine)
    scenarios/
      __init__.py                   Scenario protocol + registry
      reconciliation.py             the seed task, now a registered plugin
    viz/
      console.py  report.py         (was viz.py, split)
      assets/                       report template + vendored d3
    web/
      app.py                        FastAPI: REST + SSE (NEW)
      static/                       SPA (D3 force layout, live token/cost/latency)
    telemetry.py                    OTel GenAI span/metric emission (NEW, optional dep)
  cassettes/                        VERSIONED recorded interactions (NEW)
    v1/reconciliation/orchestrator.sonnet.t0.jsonl
    v1/reconciliation/blackboard.sonnet.t0.jsonl
    v1/reconciliation/hybrid.sonnet.t0.jsonl
    MANIFEST.json                   sha256 per cassette, schema_version, model, temp, recorded_at
  tests/
    test_smoke.py  test_gate_property.py  test_golden_cassette.py
    test_fairness.py  test_web_backend.py  conftest.py
  docs/                             mkdocs sources (RESEARCH/WHEN-TO-USE/architecture + DX pages)
  output/.gitkeep
```

Rationale for src layout: it forces the installed-package import path in tests/CI (catches "works from repo root, breaks when installed"), and it cleanly separates the shipped library from `cassettes/`, `docs/`, `output/`. The seed's `PYTHONPATH := $(CURDIR)` hack in the Makefile disappears — `uv run` puts the package on the path.

#### Packaging (uv + PEP 621, pinned)

`pyproject.toml` uses `[project.optional-dependencies]`/dependency-groups so the base install stays stdlib-only:

- base deps: none (Mock + cassette replay need only stdlib json).
- `real`: `anthropic>=0.40`.
- `web`: `fastapi`, `uvicorn[standard]`, `sse-starlette`.
- `otel`: `opentelemetry-sdk`, `opentelemetry-exporter-otlp`.
- `viz`: `rich` (console tables; optional — plain fallback if absent).
- `dev`: `pytest`, `pytest-asyncio`, `hypothesis`, `ruff`, `mypy`, `httpx` (test client), `mkdocs-material`, `mkdocstrings[python]`.
- `all`: union.

`[project.scripts] ovb = "ovb.cli:app"`. `uv.lock` is committed; CI runs `uv sync --frozen`. `.python-version` pins 3.13. This is the reproducibility floor: locked deps + pinned interpreter + versioned cassettes.

#### Config (pydantic-settings + .env)

`ovb/config.py` exposes a nested `Settings` (env prefix `OVB_`, nested delimiter `__`), loaded once and injected. This is the single source of truth for run parameters that must be *identical across engines* — the fairness guarantee is enforced here, not per-engine.

```python
class LLMSettings(BaseModel):
    mode: Literal["mock", "cassette", "real"] = "cassette"
    model: str = "claude-sonnet-5"
    temperature: float = 0.0          # fairness: temp=0 by default
    max_tokens: int = 256
    cassette_dir: Path = Path("cassettes/v1")
    record: bool = False              # real mode + record=True writes cassettes

class RunSettings(BaseModel):
    scenario: str = "reconciliation"
    runs: int = 1                     # N-run variance for real/nondeterministic
    seed: int = 0
    max_steps: int = 50               # control-unit cap, shared by all engines

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OVB_", env_nested_delimiter="__",
                                      env_file=".env")
    llm: LLMSettings = LLMSettings()
    run: RunSettings = RunSettings()
    otel_enabled: bool = False
```

`temperature`, `model`, `max_steps` live on `Settings`, so no engine can silently use different sampling — CLI flags mutate the shared object, both engines read it.

#### The cassette layer (the load-bearing piece)

`ovb/cassette.py` implements record/replay keyed by a **content hash of the request**. The request key is `sha256` over a canonical JSON of `(model, temperature, max_tokens, system, messages)` — everything that determines Claude's output distribution. A cassette is a JSONL file (one entry per unique request) so it diffs cleanly in review and appends deterministically during recording:

```
{"key":"9f2c…","request":{"model":"claude-sonnet-5","temperature":0.0,
  "max_tokens":256,"system":"You are the Scope owner…","messages":[…]},
 "response":{"text":"Scope: adjusting scope->8.",
  "usage":{"input_tokens":412,"output_tokens":9,
           "cache_creation_input_tokens":0,"cache_read_input_tokens":0}},
 "meta":{"stop_reason":"end_turn","recorded_at":"2026-06-30T…","sdk":"anthropic 0.42"}}
```

`CassetteLLM(inner, store, mode)` wraps *any* LLM and implements the same `complete(system, prompt, expect)` contract:
- **replay**: compute key, look up; on hit return the recorded `Completion` (real usage numbers). On miss, in strict replay raise `CassetteMiss(key, request)` with a copy-pasteable `ovb record` hint — a miss is a *test failure*, never a silent live call.
- **record**: call the wrapped `ClaudeLLM`, persist `(key → response)` including the **full usage block** (input/output/cache_creation/cache_read), return the live `Completion`.
- **replay-or-record** (dev convenience): hit → replay; miss → record. Never default in CI.

For N-run variance with temp=0, real Claude is *near*-deterministic but not guaranteed. The cassette stores a **list of responses per key** and replays round-robin, so `runs=5` replays the 5 recorded samples and the variance stats are real, not synthesized. `MANIFEST.json` records `sha256` of each cassette file, `schema_version`, model, temperature, and `recorded_at`; the golden test asserts the manifest matches on disk (tamper/staleness detection).

`ClaudeLLM` is upgraded to stream (`stream=True`) and read usage from `message_start` + the **final cumulative** `message_delta.usage` — critically *not* summing deltas (they are cumulative; summing double-counts cache tokens, a known ecosystem bug). Latency is real wall-clock; `latency_for()` keeps synthesizing a token-proportional value only in pure-mock mode.

#### CLI surface (typer)

```
ovb bench     [--scenario S] [--engines o,b,h] [--runs N] [--mode cassette|mock|real]
              [--model M] [--temperature T] [--html/--no-html] [--json out.json]
ovb run ENGINE [--scenario S] …        one engine, prints trace + WORM log
ovb record    [--scenario S] [--engines …] [--model …] [--temperature 0]
              records/refreshes cassettes; requires real mode + key
ovb replay-check                       assert no engine×scenario has a cassette miss (CI gate)
ovb serve     [--host --port --reload] launches the web app (uvicorn)
ovb scenarios | ovb engines | ovb agents            list registered plugins
ovb doctor                             prints resolved Settings, cassette manifest status, key presence
ovb version
```

`bench --runs N --mode cassette` is the default demo. `ovb doctor` is the DX safety net: it tells you *why* you're in mock vs cassette vs real and whether cassettes are present/valid.

#### Web app launch

`ovb serve` boots FastAPI (uvicorn). Backend contract:
- `POST /api/runs` `{scenario, engines, runs, mode, model, temperature}` → `{run_id}`.
- `GET /api/runs/{id}/events` → **SSE** stream of typed events (`call`, `write`, `gate`, `done`) as they happen, so the D3 force graph animates state writes rippling to subscribed agents and the token/cost/latency meters tick live. SSE (not WebSocket) because the stream is server→client only, unidirectional, and survives proxies trivially — matches the append-only WORM/Recorder model exactly.
- `GET /api/runs/{id}/report` → the self-contained HTML.
- Static SPA served from `web/static`. In cassette mode the whole thing runs offline, so the flagship visualization works with no key — this is the demo that sells the repo.

#### Testing

- `test_smoke.py`: both engines converge, gate passes, `is_consistent()` true (mock mode, no artifacts).
- `test_gate_property.py` (**Hypothesis**): for random valid initial states, *every* engine terminates within `max_steps` and lands on a state where `is_consistent()` holds; also the metamorphic property **orchestrator, blackboard, and hybrid reach the identical final state** for the same start. This is the fairness invariant as an executable property.
- `test_golden_cassette.py`: run all three engines against the committed `v1` cassette in **strict replay**; assert (a) zero cassette misses, (b) identical final gate state across engines, (c) recorded aggregate metrics match a checked-in golden (calls/tokens per engine) within tolerance, (d) `MANIFEST.json` sha256s match files on disk. This is the "both engines reach the same gate on real recorded data" guarantee.
- `test_fairness.py`: asserts all engines saw the same `(model, temperature, max_tokens)` and the same agent set/scenario — guards against topology getting an unfair sampling edge.
- `test_web_backend.py`: `httpx.ASGITransport` client drives `POST /api/runs` + consumes the SSE stream in cassette mode; asserts the terminal `done` event carries a consistent gate. No server process, no network.

#### CI (GitHub Actions)

Single `ci.yml`, matrix on 3.13 (+3.12 tolerance):
1. `uv sync --frozen --all-extras`
2. `uv run ruff check` + `ruff format --check`
3. `uv run mypy src`
4. `uv run pytest -q` (includes property + golden-cassette + web-backend, all offline)
5. `uv run ovb replay-check` — hard gate: any cassette miss fails CI (prevents drift between code prompts and recorded cassettes)
6. `uv run mkdocs build --strict`
A separate **manual** `record.yml` (workflow_dispatch, uses `ANTHROPIC_API_KEY` secret) refreshes cassettes and opens a PR — real calls never run on every push, only intentionally.

#### Plugin registration (scenarios / agents / engines)

Three registries via decorators so the kernel never changes when you extend it:

```python
@register_engine("blackboard")
def make(settings) -> Engine: ...
@register_scenario("reconciliation")
def make() -> Scenario: ...   # provides initial state, gate, agent factory
```

`Engine` is a `Protocol`: `run(scenario, llm, recorder, settings) -> FinalState`. `Scenario` provides `initial_state()`, `is_consistent(state)`, `build_agents()`. New contributions land as a file in `engines/` or `scenarios/` plus one decorator; `ovb engines`/`ovb scenarios` discover them via entry points (`[project.entry-points."ovb.engines"]`) *and* local module import, so third-party packages can register out-of-tree. Adding a scenario requires recording its cassettes (`ovb record --scenario new`) before the golden test will pass — CONTRIBUTING documents this as the definition of done.

#### Reproducibility guarantees (summary)

Pinned interpreter (`.python-version`) + locked deps (`uv.lock`, `--frozen`) + versioned cassettes (`cassettes/v1` + sha256 `MANIFEST`) + temp=0 default + `replay-check` CI gate. A checkout at a given commit produces byte-identical demo output offline, forever, while `--mode real` still yields genuine live numbers on demand.

#### Interfaces & contracts
##### `ovb/config.py`
```python
class LLMSettings(BaseModel):
    mode: Literal["mock","cassette","real"] = "cassette"
    model: str = "claude-sonnet-5"
    temperature: float = 0.0
    max_tokens: int = 256
    cassette_dir: Path = Path("cassettes/v1")
    record: bool = False

class RunSettings(BaseModel):
    scenario: str = "reconciliation"
    engines: list[str] = ["orchestrator","blackboard","hybrid"]
    runs: int = 1
    seed: int = 0
    max_steps: int = 50

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OVB_", env_nested_delimiter="__", env_file=".env")
    llm: LLMSettings = LLMSettings()
    run: RunSettings = RunSettings()
    otel_enabled: bool = False

def load_settings(**overrides) -> Settings: ...
```

##### `ovb/llm.py` (evolved) — usage now carries cache tokens
```python
@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    @property
    def total(self) -> int: ...          # input + output (billable-context view)
    def __add__(self, other: "Usage") -> "Usage": ...

@dataclass
class Completion:
    text: str
    usage: Usage
    latency_ms: float = 0.0
    stop_reason: str = ""

class LLM(Protocol):
    name: str
    def complete(self, system: str, prompt: str, expect: str = "") -> Completion: ...

class ClaudeLLM:                          # streams; reads CUMULATIVE final usage, never sums deltas
    def __init__(self, model: str, temperature: float, max_tokens: int): ...

def build_llm(settings: Settings) -> LLM:  # mock | cassette(inner=Claude) | real(Claude)
    ...
```

##### `ovb/cassette.py`
```python
def request_key(model: str, temperature: float, max_tokens: int,
                system: str, messages: list[dict]) -> str:      # sha256 of canonical JSON

class CassetteMiss(Exception):
    key: str; request: dict                                     # message includes `ovb record` hint

class CassetteStore:
    def __init__(self, path: Path): ...
    def get(self, key: str) -> list[CassetteEntry]: ...         # round-robin over N recorded samples
    def append(self, entry: CassetteEntry) -> None: ...
    def manifest_ok(self) -> bool: ...                          # sha256 vs MANIFEST.json

class CassetteLLM:                                              # implements LLM
    def __init__(self, inner: LLM, store: CassetteStore,
                 mode: Literal["replay","record","replay_or_record"]): ...
```
Cassette JSONL entry schema:
```json
{"key":"<sha256>",
 "request":{"model":"claude-sonnet-5","temperature":0.0,"max_tokens":256,
            "system":"…","messages":[{"role":"user","content":"…"}]},
 "response":{"text":"…",
   "usage":{"input_tokens":412,"output_tokens":9,
            "cache_creation_input_tokens":0,"cache_read_input_tokens":0},
   "stop_reason":"end_turn"},
 "meta":{"recorded_at":"<iso8601>","sdk":"anthropic 0.42","schema_version":1}}
```
`cassettes/v1/MANIFEST.json`:
```json
{"schema_version":1,"model":"claude-sonnet-5","temperature":0.0,
 "files":{"reconciliation/blackboard.sonnet.t0.jsonl":{"sha256":"…","entries":7,"recorded_at":"…"}}}
```

##### `ovb/engines/__init__.py` — Engine protocol + registry
```python
class Engine(Protocol):
    name: str
    def run(self, scenario: Scenario, llm: LLM, recorder: Recorder,
            settings: Settings) -> FinalState: ...

_ENGINES: dict[str, Callable[[Settings], Engine]] = {}
def register_engine(name): ...            # decorator
def build_engine(name, settings) -> Engine: ...
def list_engines() -> list[str]: ...
```

##### `ovb/scenarios/__init__.py`
```python
class Scenario(Protocol):
    name: str
    def initial_state(self) -> dict: ...
    def is_consistent(self, state: dict) -> bool: ...   # the deterministic GATE
    def build_agents(self) -> list[Agent]: ...

def register_scenario(name): ...
def build_scenario(name) -> Scenario: ...
```

##### `ovb/web/app.py` — HTTP + SSE contract
```
POST /api/runs        {scenario,engines,runs,mode,model,temperature} -> {run_id}
GET  /api/runs/{id}/events   text/event-stream:
     event: call  data: {seq,engine,agent,usage{…cache…},latency_ms,changed,writes,trigger}
     event: write data: {seq,agent,field,old,new}
     event: gate  data: {engine,consistent:bool,steps}
     event: done  data: {engine,n_calls,n_effective,n_wasted,total_usage,total_latency_ms}
GET  /api/runs/{id}/report   text/html   (self-contained)
GET  /healthz -> {"status":"ok","mode":"cassette","cassettes":"v1"}
```

##### `ovb/telemetry.py` — OTel GenAI (experimental conventions)
Per `complete()` emit span `gen_ai.<op>` with attrs `gen_ai.provider.name=anthropic`,
`gen_ai.request.model`, `gen_ai.request.temperature`, `gen_ai.usage.input_tokens`,
`gen_ai.usage.output_tokens`; engine run wrapped in a parent span carrying `ovb.engine`,
`ovb.scenario`. No-op unless `settings.otel_enabled`.

##### CLI (typer) — signatures
```
ovb bench(scenario, engines, runs, mode, model, temperature, html, json_out)
ovb run(engine, scenario, mode, model, temperature)
ovb record(scenario, engines, model, temperature)      # needs real + key
ovb replay-check()                                      # CI gate; nonzero on any miss
ovb serve(host, port, reload)
ovb scenarios() / ovb engines() / ovb agents()
ovb doctor()                                            # resolved Settings + manifest + key status
ovb version()
```

##### Makefile / justfile targets
```
just setup    -> uv sync --all-extras
just bench    -> uv run ovb bench                 # default cassette demo, writes output/report.html
just run E    -> uv run ovb run {{E}}
just test     -> uv run pytest -q
just lint     -> uv run ruff check && uv run ruff format --check && uv run mypy src
just serve    -> uv run ovb serve
just record   -> uv run ovb record                # real calls; needs ANTHROPIC_API_KEY
just replay-check -> uv run ovb replay-check
just docs     -> uv run mkdocs serve
just ci       -> just lint && just test && just replay-check && uv run mkdocs build --strict
just clean    -> rm -rf output/*.html .pytest_cache .ruff_cache .mypy_cache
```

##### Exact quickstart (README top)
```bash
git clone <repo> && cd ovb
uv sync                       # or: uv sync --all-extras for web+docs+dev
uv run ovb bench              # offline, no key: replays cassettes, real recorded numbers,
                              #   prints comparison, writes output/report.html
uv run ovb serve             # live D3 visualization at http://127.0.0.1:8000 (still offline)

#### opt into real Claude calls — one env var + a key:
export ANTHROPIC_API_KEY=sk-ant-...
uv run ovb bench --mode real --runs 5      # true token/cost/latency, N-run variance

#### refresh the committed cassettes from real calls:
uv run ovb record --temperature 0 && uv run ovb replay-check
```

#### Risks
- **Cassette drift: an agent-prompt or scenario change silently invalidates every recorded key, and contributors don't notice until golden tests fail cryptically.** → `ovb replay-check` as a CI gate emits the exact missing keys + `ovb record` command; CONTRIBUTING makes 're-record cassettes' the definition of done for any prompt/scenario change; MANIFEST sha256 flags stale files.
- **Real Claude at temp=0 is not perfectly deterministic, so recorded cassettes can diverge from a fresh live run and confuse users comparing --mode real vs cassette.** → Store N samples per key and report variance explicitly; docs state cassettes are a frozen recording, not a guarantee live output is byte-identical; golden metrics use tolerances, not equality.
- **Prompt-injection blast radius: in the blackboard/hybrid, a poisoned write propagates to all subscribed agents via shared state — larger than the orchestrator's isolated windows.** → Agents validate numeric patches against their deterministic rule (already in agents.py), so the model can't move the plan off-gate; docs/SECURITY.md documents shared-state blast radius as an explicit honest trade-off; WORM log makes any injected write auditable.
- **Fairness leak: a future engine or CLI flag lets one topology use a different temperature/model/max_tokens.** → model/temperature/max_tokens live only on the shared Settings object read by all engines; test_fairness.py asserts identical sampling params and agent set across engines.
- **uv not installed on a reviewer's machine breaks the advertised quickstart.** → Makefile/justfile fall back to `python -m pip install -e .[all]`; README shows both `uv run ovb` and `python -m ovb` invocations; CI pins the uv version.
- **OTel GenAI conventions are still experimental (attribute names may churn).** → telemetry.py is an optional, off-by-default module isolated behind settings.otel_enabled; attribute names centralized in one place for a one-line update when the spec stabilizes.

#### Open questions
- Should hybrid record its own cassettes, or reuse orchestrator+blackboard cassettes since it composes their agent calls at identical (model,temp)? Reuse is cheaper but couples cassette validity across engines.
- Cassette storage: one JSONL per engine×scenario (clean diffs, more files) vs a single keyed store per scenario (fewer files, coarser diffs) — current design picks per-engine for review clarity; revisit if file count explodes with many scenarios.
- Do we vendor D3 into web/static for true offline, or rely on a CDN with an offline fallback? Vendoring guarantees the no-network contract but adds a bundled asset to review.
- Model id 'claude-sonnet-5' is a placeholder from the seed; confirm the exact current model string before recording the shipped v1 cassettes so the manifest is accurate.
- Should replay-check also assert cassette response text matches the agent's expected narration shape, or only that keys resolve? Stricter checking catches prompt drift earlier but couples tests to narration wording.

### 10.8 Insights, Docs & Narrative: The Teaching Layer for the Orchestrator-vs-Blackboard Reference Repo

_A concrete plan for the docs/narrative slice: a README arc built around a one-sentence thesis (where control lives + how much agents see each other's work), a seven-surface docs/ information architecture (concepts, architecture, methodology, results, when-to-use, security, myths), an auto-generated RESULTS.md + results.html rendered from a versioned benchmark JSON contract (report.json), a doc-sync CI gate that fails on drift between committed numbers and freshly computed ones, and an insights narrative that converts real metrics (calls, effective/wasted, tokens by kind incl. cache, latency, variance across N runs) into decisions. Every number a reader sees is a template placeholder resolved from report.json; no figure is hand-typed. Ties the existing cited docs/RESEARCH.md in as the "why we believe this" spine and keeps the practitioner WHEN-TO-USE.md as the payoff. Grounded in the actual kernel (Recorder/Call/Event aggregates, Usage token counts, is_consistent gate) and verified against current Anthropic usage fields and OTel GenAI semantic conventions._

#### Thesis and the through-line

Every doc surface serves one sentence, printed identically in the README, the concepts page, and the RESULTS header:

> **The topology choice is a choice about two things: where control lives (a hub vs. the state itself) and how much each agent sees of the others' work (isolated message-passing vs. one shared board). Everything downstream — calls, tokens, latency, auditability, blast radius — falls out of those two axes.**

The teaching arc is a five-beat funnel, and every page is one beat: **Thesis → Fairness → Mechanics → Evidence (both directions) → Decision.** A skeptical senior engineer must be able to traverse it in ~8 minutes and leave able to (a) restate the thesis, (b) name the one control-model diff, (c) cite a real margin *with variance*, (d) name a case where the blackboard *loses*, and (e) pick a topology for their own task. If a doc doesn't advance one of those five, it gets cut.

#### README arc (the 90-second version)

The existing README is already strong; I keep its structure but sharpen five things and make its numbers generated:

1. **Thesis block first**, above the topology SVG. One sentence (above), then the two-axis framing. No history, no framework name-drops yet — those live in RESEARCH.
2. **The "only one file differs" fairness claim, moved up** to immediately follow the thesis, because for this audience *fairness is the credibility gate*. A reader who doesn't believe the comparison is fair discards every number. So: "Same agents, same task, same gate, same model+temperature, same recorder — `git diff orchestrator.py blackboard.py` is the entire independent variable."
3. **The headline table is generated**, not hand-typed. It's a fenced block with sentinel markers (`<!-- BENCH:headline -->`) filled by `tools/render_docs.py` from `output/report.json`. The 12/908 vs 7/511 numbers become `{{orch.n_calls}}/{{orch.total_tokens}}` placeholders. Today they're hardcoded in the README prose — that is a landmine the moment `--real` numbers differ, and it's the single highest-value sync fix.
4. **A mode/provenance badge line** under the table: `mode=mock · runs=1 · git=<sha> · generated=<iso8601>` for mock, and `mode=real · model=claude-sonnet-5 · temp=0 · runs=20 · generated=<iso>` for real. This one line is what lets a reader trust the table without opening the JSON.
5. **Three honest callouts kept but promoted to first-class links**: the mock-token caveat (already present), a "read this before you build multi-agent anything" pointer to the counterpoint, and a new one-liner on injection blast-radius pointing to `docs/security.md`. The README should *advertise* the repo's intellectual honesty, because that's the differentiator versus every breathless multi-agent blog post.

README explicitly does **not** try to teach the whole model — it routes. Its job is thesis + fairness + "here's the one number, here's where to go next."

#### docs/ information architecture

Seven surfaces, each a single beat, cross-linked with a fixed footer nav so the reader always knows where they are in the funnel. Existing files map cleanly; I add four and re-scope two.

| Path | Beat | Status | One-line job |
|---|---|---|---|
| `docs/concepts.md` | Thesis | **new** | The two axes, the vocabulary (control unit, gate, KS, WORM, superstep), the topology SVG annotated. No code. |
| `docs/architecture.md` | Mechanics | exists, keep | How the two engines' ~40 lines each realize the axes; the bounded-blackboard idea. |
| `docs/methodology.md` | Fairness | **new** | The fairness contract, temp=0 + N-run + variance protocol, record/replay cassettes, token-accounting rules (incl. cache), what is and isn't held constant. This is the page skeptics attack; it must be bulletproof. |
| `docs/RESULTS.md` | Evidence | **new, generated** | Auto-rendered from `report.json`. Never hand-edited (has a "DO NOT EDIT" banner). Tables + links to `results.html`. |
| `docs/insights.md` | Evidence→Decision bridge | **new** | Converts the RESULTS numbers into claims and decisions. The narrative. Semi-generated (prose templates with injected numbers). |
| `docs/WHEN-TO-USE.md` | Decision | exists, keep | The practitioner payoff. Already excellent; add a generated "on *this* task, here's the measured margin" sidebar. |
| `docs/security.md` | Honest counterpoint | **new** | Prompt-injection blast radius in shared state, role-scoped writes, WORM as forensic control, the "message-passing contains blast radius better" tradeoff. |
| `docs/faq.md` (myths) | Honest counterpoint | **new** | "Isn't the blackboard just winning because of early-exit?" and 9 other skeptic questions, answered with the fairness controls. |
| `docs/RESEARCH.md` | Foundation | exists, keep | The cited SOTA spine. Everything else cites *into* it by section anchor. |

**Layering discipline:** RESEARCH.md is the evidence base (cited, heavy, "living document"). concepts/architecture/methodology are the *distillation* (opinionated, uncited-but-anchored-to-RESEARCH). WHEN-TO-USE/insights are the *application*. A reader can enter at any layer; each links up to its foundation and down to its application. Every non-obvious claim in the distillation layer carries an inline `→ RESEARCH §5` anchor so a skeptic can trace it to a source in one click. This is the mechanism that lets the shorter docs stay assertive without being hand-wavy.

#### The generated-results pipeline (the core of "docs stay in sync with code")

The single most important engineering decision in this slice: **no result number is ever typed by a human.** There is one source of truth — `output/report.json` — and everything else is a projection.

**Contract:** `demos/benchmark.py` gains `--json output/report.json`. It serializes both `Recorder`s plus a run-metadata header into a versioned schema (see Interfaces). The recorder already exposes exactly the aggregates needed (`n_calls`, `n_effective`, `n_wasted`, `total_usage`, `total_latency_ms`, `n_writes`) plus per-`Call` and per-`Event` detail, so serialization is a thin dump, not new computation. Token detail extends `Usage` to carry the four Anthropic fields (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`) so real-mode cost is honest; mock mode fills only prompt/completion and marks `cache=null`.

**Renderers** (`tools/render_docs.py`, stdlib-only, no Jinja to preserve the zero-dep promise): a tiny sentinel-based templater. Markdown files contain `<!-- BENCH:headline START -->…<!-- BENCH:headline END -->` regions; the renderer replaces the region body with a table built from `report.json`. `RESULTS.md` is fully generated (whole body between one sentinel pair). README and WHEN-TO-USE have *embedded* generated regions inside otherwise hand-written prose. `results.html` is generated by extending the existing `viz.render_html` — it already renders both traces and the WORM log; I add the variance band, the token-by-kind stacked bar, and the metadata badge.

**Sync enforcement (the CI gate):** `tools/check_docs_sync.py` runs `render_docs` into a temp dir and `diff`s against committed files; nonzero diff → nonzero exit. Wired into `make docs` (regenerate) and `make check` (verify, used in CI). This makes drift a *build failure*, not a code-review catch. A `pre-commit` hook runs the same check on staged `.md`. The mental model for contributors: **you don't edit numbers, you run `make docs`.** This is the same pattern as generated API docs or `go generate` — familiar to the audience, and the only thing that actually keeps 47 numbers across 6 files honest as the task/agents evolve.

**Determinism for CI:** mock mode is fully deterministic, so the committed `report.json` and rendered docs are reproducible byte-for-byte and CI checks them offline with no key. Real-mode numbers are *not* committed as canonical (they'd flake); instead real runs write a *separate* `report.real.json` under `output/` (gitignored) and the docs show mock numbers with a "run `--real` for API-measured numbers" affordance. The one exception: a curated, checked-in `benchmarks/real_YYYYMMDD.json` snapshot (produced via the cassette layer, below) that RESULTS.md renders in a "Real-model run (recorded)" section so readers see genuine token/latency/cache numbers without a key. That snapshot is refreshed deliberately, dated, and provenance-stamped — never auto-overwritten.

#### Record/replay cassettes and the N-run variance protocol (fairness made real)

Real LLMs are nondeterministic, so a single real run proves nothing and a skeptic will say so. Methodology.md specifies and the tooling enforces:

- **temp=0** on both engines (necessary, not sufficient — Claude at temp=0 is still not bitwise-deterministic).
- **N runs (default 20)** per engine, reporting **median, IQR, and min–max** for every metric, not just a point estimate. `benchmark.py --real --runs 20` loops and the JSON carries a `distribution` block per metric. RESULTS.md renders **"blackboard used 1.71× fewer calls (median; IQR 1.68–1.74, n=20)"** — a margin with a variance band is credible; a bare ratio is not.
- **Cassette record/replay** (`ovb/cassette.py`): a `--record` run captures every `(system, prompt) → (text, usage)` to `benchmarks/cassettes/*.jsonl` keyed by a hash of the request; `--replay` (the default when a cassette exists and no key is set) serves recorded completions. This gives three properties at once: (1) offline reproducibility of *real* numbers for docs and CI, (2) a frozen artifact a skeptic can inspect and re-run, (3) a clean seam to demonstrate the record/replay pattern itself. The cassette is the bridge that lets "REAL" and "reproducible offline" coexist — the JSON snapshot in RESULTS is rendered from a replayed cassette run.

The variance story *is* the fairness story for a real-LLM comparison, so methodology.md leads with it and insights.md never states a margin without its band.

#### The insights narrative (metrics → decisions)

`insights.md` is where the repo earns "flagship." It is not a metrics dump; it's an argument built on the generated numbers, in five moves:

1. **The headline, framed as a mechanism, not a result.** "The blackboard's win isn't magic — it's the *absence of the hub tax*. The orchestrator's `{{orch.n_wasted}}` no-op calls are the price of detecting 'done' without shared state." Number injected; sentence stable.
2. **Decompose the win honestly.** A generated waterfall: total-token delta = (fewer calls) × (per-call cost) − (larger shared-state prompts). This pre-empts the skeptic's best objection — "the blackboard's prompts are bigger because everyone sees the whole board." We show the *net* and name the tradeoff. If shared-state prompt growth ever eats the call savings on a variant task, the narrative says so, because it's generated from real numbers.
3. **The early-exit control.** Explicitly: "Does the blackboard win only because it early-exits on the gate? We tested it: `orchestrator_early_exit=on` variant still costs `{{...}}` because the hub must *complete a sweep* to know a sweep was clean. The topology, not the exit policy, drives the delta." This is the FAIRNESS principle made falsifiable — and the myth it kills is the first one a senior engineer raises.
4. **The reversal.** A second scenario (`task_linear.py`, a classify→route→answer pipeline) where the **orchestrator wins**, with generated numbers. A comparison that only ever shows one side winning is marketing; showing the crossover is what makes it a lab. insights.md renders both scenarios' margins side by side and states the boundary condition (interdependence coupling) that flips the sign.
5. **The decision handoff.** Ends by routing to WHEN-TO-USE's checklist, now annotated with "on the task where we measured it, this bullet cost X."

Each move is a prose template with `{{}}` slots; `render_docs` fills them. If numbers move, the *argument* stays valid and the figures update — the narrative can't silently go stale.

#### Diagrams

The topology SVG exists and is good. I add four, all generated or checked-in-with-a-generator so they can't drift:

1. **Annotated topology** (hand-authored SVG, `docs/images/topologies_annotated.svg`): the existing diagram with the two axes labeled (control locus, visibility) and the "hub tax" / "ripple" arrows called out. Used in concepts.md.
2. **Call-trace timeline** (generated, `output/trace_timeline.svg`): a horizontal swimlane per agent, one tick per `Call`, colored effective/wasted, for both engines stacked — literally *shows* the 5 wasted orchestrator ticks vs. the blackboard's tight ripple. Generated from `report.json` calls array.
3. **Token-by-kind stacked bar** (generated, in results.html): input / output / cache_creation / cache_read per engine — makes the real-mode cache story visible.
4. **Variance band chart** (generated, in results.html): per-metric median with IQR whiskers across the N runs. This is the single most credibility-bearing figure for the real-mode claim.

The dynamic step/token/cost/latency visualization (D3 force layout, the "in action" replay) is another slice's deliverable; my docs *link to it and explain how to read it*, and results.html is the static, no-JS-needed fallback so the numbers survive even where the interactive viz can't run.

#### Keeping RESEARCH.md tied in and alive

RESEARCH.md is the credibility spine and stays the citation authority. Three integrations: (1) every distilled claim in the shorter docs carries a `→ RESEARCH §N` anchor, and a `tools/check_anchors.py` verifies those anchors resolve (so a RESEARCH re-run that renumbers sections breaks the build rather than silently orphaning links); (2) RESEARCH's own "living document / re-run the workflow" header gets a dated provenance stamp consistent with the report.json metadata style; (3) the repo's headline claims (fewer calls on interdependent work, ~15× token multiplier caveat, reasoning-model-substitution caveat) each get a "measured here → RESEARCH says → your task" triangulation in insights.md, so the local experiment and the literature reinforce rather than float apart.

#### Why this is worthy of a flagship

The bar for a skeptical senior engineer is not "pretty docs" — it's *"can I break the claim?"* This design is built to survive that: fairness is a documented, enforced contract; every number is generated and provenance-stamped; variance is reported, not hidden; the counter-cases (orchestrator wins, early-exit doesn't explain it, blackboard's bigger prompts, injection blast radius, reasoning-models-substitute) are *first-class pages*, not buried caveats; and the whole thing stays honest under change because drift is a build failure. The narrative converts each metric into a decision, and the decision routes back to the reader's own task. That combination — reproducible real numbers, adversarial honesty, and a tight thesis-to-decision funnel — is what a reference repo needs to be cited rather than skimmed.

#### Interfaces & contracts
##### `output/report.json` — the single source of truth (schema v1)

```jsonc
{
  "schema": "ovb.report/1",
  "generated_at": "2026-07-01T21:30:00Z",
  "git_sha": "a94e077",
  "mode": "mock",                      // "mock" | "real" | "replay"
  "model": "claude-sonnet-5",          // null in mock
  "temperature": 0,
  "runs": 1,                            // N for real/replay variance
  "scenario_id": "reconcile",           // matches task module
  "scenario_text": "Project-plan reconciliation ...",
  "consistent_final_state_match": true, // both engines reached same gate-passing state
  "engines": {
    "orchestrator": <EngineReport>,
    "blackboard":   <EngineReport>
  },
  "comparison": {                       // precomputed so no renderer does math
    "n_calls":      {"orch": 12, "bb": 7, "ratio": 1.714, "winner": "blackboard"},
    "total_tokens": {"orch": 908, "bb": 511, "ratio": 1.777, "winner": "blackboard"},
    "n_wasted":     {"orch": 5,  "bb": 0, "winner": "blackboard"},
    "latency_ms":   {"orch": 90.8, "bb": 51.1, "ratio": 1.777, "winner": "blackboard"}
  }
}
```

```jsonc
// EngineReport
{
  "engine": "blackboard",
  "aggregates": {
    "n_calls": 7, "n_effective": 7, "n_wasted": 0, "n_writes": 6,
    "usage": {"input_tokens": 430, "output_tokens": 81,
              "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
              "total": 511},
    "latency_ms": 51.1
  },
  // present only when runs>1 (real/replay); per-metric distribution:
  "distribution": {
    "n_calls":      {"median": 7, "iqr": [7, 7],   "min": 7,  "max": 8},
    "total_tokens": {"median": 511, "iqr": [503, 522], "min": 498, "max": 540},
    "latency_ms":   {"median": 812.0, "iqr": [740, 905], "min": 690, "max": 1210}
  },
  "calls": [ <CallRecord>, ... ],       // from Recorder.calls
  "events": [ <EventRecord>, ... ]      // WORM log, from Recorder.events
}
```

```jsonc
// CallRecord (serialized ovb.instrumentation.Call)
{"seq": 3, "agent": "Timeline", "trigger": "budget changed",
 "changed": true, "writes": {"timeline_weeks": 14},
 "usage": {"input_tokens": 62, "output_tokens": 11, "total": 73},
 "latency_ms": 7.3}

// EventRecord (serialized ovb.instrumentation.Event)
{"seq": 4, "agent": "Timeline", "field": "timeline_weeks", "old": 12, "new": 14}
```

##### Serialization hook (thin, added to instrumentation)

```python
#### ovb/instrumentation.py
def report(self) -> dict:
    """Recorder -> EngineReport dict. No new computation; dumps aggregates+calls+events."""

#### ovb/report.py  (new)
def build_report(orch: dict, bb: dict, *, mode: str, model: str|None,
                 temperature: float, runs: int, distributions: dict|None) -> dict: ...
def write_report(report: dict, path: str) -> None: ...        # json.dump, sorted keys
```

##### `Usage` extension (honest real-mode tokens; back-compat)

```python
@dataclass
class Usage:
    prompt_tokens: int = 0            # == input_tokens (kept for back-compat)
    completion_tokens: int = 0        # == output_tokens
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    # ClaudeLLM.complete fills all four from msg.usage.*
    # MockLLM fills only prompt/completion; cache_* stay 0
```

Anthropic `msg.usage` fields consumed (verified current): `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens` (+ `cache_creation.ephemeral_5m_input_tokens`/`ephemeral_1h_input_tokens` if caching is enabled later).

##### Doc-generation tooling (stdlib-only)

```
tools/render_docs.py       # report.json -> fills <!-- BENCH:<id> START/END --> regions
                           #   in README.md, docs/RESULTS.md, docs/WHEN-TO-USE.md,
                           #   docs/insights.md; renders docs/images/*.svg; extends viz.render_html
tools/check_docs_sync.py   # render into tmp, diff vs committed; nonzero exit on drift
tools/check_anchors.py     # verify every "→ RESEARCH §N" anchor resolves
```

Sentinel convention (works in Markdown, HTML, and SVG comments):
```
<!-- BENCH:headline START (generated by tools/render_docs.py — do not edit) -->
... generated table ...
<!-- BENCH:headline END -->
```
Placeholder mini-syntax inside prose templates: `{{orch.n_calls}}`, `{{comparison.total_tokens.ratio|round2}}`, `{{bb.distribution.n_calls.iqr}}`.

##### CLI surface (extends existing demos/benchmark.py)

```
python demos/benchmark.py --json output/report.json          # mock, deterministic
python demos/benchmark.py --real --runs 20 --json output/report.real.json
python demos/benchmark.py --record benchmarks/cassettes/reconcile.jsonl   # capture
python demos/benchmark.py --replay benchmarks/cassettes/reconcile.jsonl \
                          --json benchmarks/real_20260701.json            # offline real numbers
python demos/benchmark.py --scenario linear                  # the reversal case
```

##### Make targets / CI

```makefile
docs:   ; python tools/render_docs.py output/report.json      # regenerate all docs+figures
check:  ; python tools/check_docs_sync.py && python tools/check_anchors.py && python tools/render_docs.py --verify
bench-real: ; python demos/benchmark.py --replay benchmarks/cassettes/reconcile.jsonl --runs 20 --json benchmarks/real_$(shell date +%Y%m%d).json
```
CI job: `make test && make check` — mock-only, offline, no key; fails on any doc/number drift or broken RESEARCH anchor.

##### Cassette layer

```python
#### ovb/cassette.py
class Cassette:
    def key(self, system: str, prompt: str) -> str: ...       # sha256 of canonicalized request
    def record(self, key, completion) -> None                 # append JSONL
    def replay(self, key) -> Completion | None
#### ovb/llm.py: get_llm(real, model, cassette=None) wraps ClaudeLLM in record/replay when set;
#### replay is the default in --real when a cassette exists and ANTHROPIC_API_KEY is unset.
```

##### Files: new vs. touched
- **New docs:** `docs/concepts.md`, `docs/methodology.md`, `docs/RESULTS.md` (generated), `docs/insights.md` (generated), `docs/security.md`, `docs/faq.md`.
- **New tools:** `tools/render_docs.py`, `tools/check_docs_sync.py`, `tools/check_anchors.py`.
- **New lib:** `ovb/report.py`, `ovb/cassette.py`; `Recorder.report()` in `ovb/instrumentation.py`.
- **Touched:** `README.md` (thesis + generated regions), `docs/WHEN-TO-USE.md` (measured-margin sidebar), `ovb/llm.py` (Usage cache fields, cassette wiring), `demos/benchmark.py` (`--json/--runs/--record/--replay/--scenario`), `ovb/viz.py` (render_html extensions), `Makefile`.
- **Untouched authorities:** `docs/RESEARCH.md` (spine), `docs/architecture.md` (mechanics — minor cross-links only).

#### Key decisions
- **Single source of truth: output/report.json, and no result number is ever hand-typed in any doc.** — The stated non-negotiable is that docs stay in sync with code. A versioned JSON contract + sentinel-region renderer + CI diff-gate makes drift a build failure rather than a review catch. The current README already hardcodes 12/908 vs 7/511 in prose — a latent inconsistency the moment --real numbers differ. _(alt: Hand-maintained tables (drift-prone); a docs framework like MkDocs+macros (violates the stdlib-only/zero-dep promise); Jupyter-rendered notebooks (heavier, harder to diff in CI).)_
- **Report every real-mode margin with a variance band (median + IQR + min/max over N=20 temp=0 runs), never a bare ratio.** — Real LLMs are nondeterministic; a senior engineer discards a single-run claim. The FAIRNESS and REAL principles both demand temp=0 + N runs + variance. The band is what makes the claim credible. _(alt: Single real run (not defensible); temp=0 alone (still not bitwise-deterministic); mean+stddev (IQR is more robust to the occasional runaway run).)_
- **Ship a record/replay cassette layer and render RESULTS' real numbers from a replayed, checked-in cassette snapshot.** — Reconciles REAL with reproducible-offline: readers and CI see genuine token/latency/cache numbers without a key, and skeptics can inspect and re-run the frozen artifact. Also demos the record/replay pattern itself. _(alt: Live real calls in CI (flaky, costs money, needs a key); mock-only numbers in RESULTS (fails the REAL principle); committing raw real report.json (flakes on every regeneration).)_
- **Make the counter-cases first-class pages, not buried caveats: orchestrator-wins scenario, early-exit-doesn't-explain-it control, blackboard's-bigger-prompts waterfall, injection blast-radius (security.md), reasoning-model substitution (faq/insights).** — The HONEST principle, and the fact that credibility with skeptics comes from showing where your own claim breaks. A comparison that only ever shows one winner reads as marketing. _(alt: One 'limitations' section (too easy to skim past); footnotes (signals the caveats are afterthoughts).)_
- **Three-layer doc stack (RESEARCH = cited evidence spine; concepts/architecture/methodology = opinionated distillation with inline →RESEARCH §N anchors; WHEN-TO-USE/insights = application), with anchor-resolution checked in CI.** — Lets the short docs be assertive without being hand-wavy — every non-obvious claim is one click from a source. Anchor-checking prevents a RESEARCH re-run from silently orphaning links. _(alt: Inline citations everywhere (bloats the distillation, duplicates RESEARCH); no anchors (skeptics can't trace claims); single mega-doc (no entry-point flexibility).)_
- **Extend Usage with the four Anthropic token kinds (input/output/cache_creation/cache_read) and render a token-by-kind bar.** — The REAL principle explicitly lists cache_creation/cache_read. Honest real-mode cost accounting requires them, and cache tokens are where a shared-state board's repeated context could get cheap — a real insight the viz should surface. _(alt: Track only total tokens (hides the cache story, understates real-mode nuance).)_
- **results.html (static, no-JS) is the canonical evidence artifact; the dynamic D3 viz (another slice) is linked as the 'in action' experience.** — Numbers must survive where the interactive viz can't run (email, GitHub preview, CI artifact). Also cleanly separates my slice's deliverable from the visualization slice's. _(alt: Only the interactive viz (fragile, unshareable as a static reference); duplicating chart logic in both (drift risk).)_

#### Risks
- **Real-mode numbers drift run-to-run enough that a committed cassette snapshot becomes misleading or a reviewer distrusts it as cherry-picked.** → Snapshots are dated, provenance-stamped (git sha, model, temp, N), rendered from a re-runnable cassette anyone can replay, and always shown with the IQR band. RESULTS states the refresh date and that the cassette is the exact frozen artifact.
- **The stdlib-only sentinel-templater is too weak for the richer generated regions (waterfalls, variance tables), tempting a Jinja/pandas dependency that breaks the zero-dep promise.** → Keep generated regions to tables + pre-rendered SVG built with plain string formatting; precompute all math in ovb/report.py (comparison block) so the renderer only substitutes, never computes. If a region needs logic, it lives in Python, not the template.
- **The CI doc-sync gate becomes a friction point contributors route around (editing generated files by hand, committing stale numbers).** → DO-NOT-EDIT banners in every generated region, a pre-commit hook that runs the same check locally, a one-command `make docs` fix path, and a failing-CI message that says exactly 'run make docs'.
- **Numbers in the injected narrative (insights.md) go stale relative to the argument — e.g. a task change flips a sign and a template sentence becomes false ('the blackboard wins because...').** → Templates assert mechanisms and inject signed comparisons (winner field from report.json), not hardcoded directions; the waterfall and reversal sections read winner/ratio from JSON so the prose flips with the data. A test asserts each narrative claim's directional invariant against the current report.
- **Scope creep: the docs slice starts re-implementing the visualization slice's charts, causing duplication and drift.** → Hard boundary: my slice owns the static report.json→SVG/HTML projection and the narrative; the interactive D3 viz consumes the same report.json but is a separate deliverable. results.html is the shared static contract both can point to.

#### Open questions
- Should the checked-in real-model snapshot live in the repo (readers get numbers with zero setup, but it dates the repo) or be fetched/regenerated on demand (fresher, but requires a key)? Leaning: commit one dated snapshot AND document regeneration.
- N=20 default for variance runs — is that enough for Claude at temp=0 given occasional long-tail runaway sweeps, or should the default be higher (30–50) with an explicit outlier-reporting policy?
- Do we want a second interdependent scenario beyond reconcile+linear (e.g. a 6-agent constraint problem) to show the margin scaling with coupling degree, or does that dilute the 'tiny, one-variable' clarity the repo is built on?
- Should security.md include a runnable injection demo (a poisoned board entry that visibly re-triggers N agents in the trace) — high impact for the blast-radius point, but adds an adversarial code path to maintain and keep from looking like an exploit kit?
- How aggressively to track OTel GenAI semantic conventions (gen_ai.usage.input_tokens, gen_ai.operation.name) given they're still experimental (v1.41, March 2026) — emit them now for observability credibility, or document the mapping and defer emission until they stabilize?

## 11. Adversarial review & resolutions
_A skeptical principal-engineer pass over all slices; findings were fed into the synthesis above._

### Contradictions found (resolved in the synthesis)
- USAGE SCHEMA — five incompatible definitions all claiming to be ovb/llm.py's Usage and all claiming back-compat: S1/S3 = {input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens}; S2 = {input_tokens, output_tokens, cache_write_5m_tokens, cache_write_1h_tokens, cache_read_tokens} (5 fields, splits ephemeral 5m/1h, prompt_tokens is a computed SUM of 4 buckets); S6 = {prompt_tokens, completion_tokens, cache_creation_tokens, cache_read_tokens}; S8 = {prompt_tokens, completion_tokens, cache_creation_input_tokens, cache_read_input_tokens}; S5 = {input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens} with total_input property. These cannot all be the same dataclass — field names, count, and the meaning of prompt_tokens differ. Any cassette JSON written with one field set fails to deserialize under another.
- PROMPT-CACHE FAIRNESS STANCE — three slices take mutually exclusive positions. S1: 'Prompt caching is ENABLED by marking the static role/preamble with cache_control; cache_read savings accrue equally and don't bias the comparison.' S2: caching is OFF by default and is 'the ONLY mode used for the headline margin'; enabling it 'would silently credit the orchestrator and violate NON-NEGOTIABLE #1.' S5: 'the orchestrator's fresh-context-per-call pattern gets NO cache benefit, while the blackboard's shared context CAN be prompt-cached' — asserting caching favors the BLACKBOARD, the opposite of S2's claim that it favors the orchestrator. The repo cannot ship all three; the headline number depends on which is true.
- CASSETTE KEY — six incompatible digests: S1 hashes (model|temp|system|prompt|tool_defs); S2 (model+temp+system+prompt+max_tokens+cache_mode), explicitly EXCLUDING expect; S3 (model|temp|system|prompt|SEED); S5 (model+system+prompt+max_tokens) with NO temperature; S7 (model,temp,max_tokens,system,messages); S8 (system,prompt only). A cassette recorded by any one slice's layer is a guaranteed CassetteMiss under any other. S3 includes seed and S5 omits temperature — both break the others' hit logic.
- CASSETTE REPLAY LATENCY SEMANTICS — S2 replays latency from recorded wall_ms ('not re-clocked'); S3 replays the recorded CHUNK STREAM 'with synthetic inter-chunk delays' (re-timed); S1 returns 'synthetic-but-recorded latency.' These produce different wall_ms on replay, so the S4 'money shot' race animation (which sums latency_ms into t_virtual_ms) is not reproducible across the slices' own replay implementations.
- SEQ / CLOCK CONTRACT — S3 defines seq as uint64 starting at 0, gap-free, doubling as SSE id and virtual-clock driver (ts_mono_ns += usage.total). S4 defines the shared clock as t_virtual_ms = cumulative sum of recorded latency_ms, and seq as 'monotonic per run' with envelope field `v:1` (integer) while S3 uses `v:'ovb.events/1'` (string). The two event envelopes are byte-incompatible (S3 nests everything under attributes{}; S4 uses a flat data{} with kind not type), yet both claim to be THE one wire event consumed by the same UI.
- SEQUENCER COUNTER BUG (S1): Sequencer.commit does `self._n += 1` for the call, then calls apply_patch(seq_fn=self.next) where next() ALSO does `self._n += 1` per WriteEvent. So call-seq and write-event-seq share one counter and the increments interleave non-deterministically per patch size — WriteEvent.seq values and the call seq are not two independent monotonic streams as the WORM log design (S3 separate write_id vs seq) assumes. The seed correctly keeps _seq and _eseq separate; the redesign merges them and corrupts both.
- ENGINE SIGNATURE — S1/S3 define Engine.run as async with keyword-only injected deps (registry, gate, initial, llm, config, rec) returning EngineResult. S5 defines run(scenario, llm, real=False, max_rounds/max_steps=...) -> RunResult (sync, positional, Scenario-based, no registry/gate injection). S7 defines Engine.run(scenario, llm, recorder, settings) -> FinalState (sync, no gate, returns bare state). Three incompatible Engine protocols; the harness (S5), the DX registry (S7), and the core (S1) cannot all be right.
- BLACKBOARD SCHEDULING CHANGES THE HEADLINE NUMBER — I ran it: the seed's FIFO single-pop + gate-after-each-commit gives 7 calls / 0 wasted / 511 tokens. S1's redesigned 'gather the whole frontier concurrently against a snapshot, commit sorted by registry index' gives 9 calls (verified by simulation) because concurrently-gathered agents read a stale snapshot that doesn't reflect same-batch commits. S8 pins 7/511 as the committed golden and S4's money shot renders the bar 'stops at ~511'; S1's own redesign breaks both.
- TEMPERATURE OWNERSHIP — S2 says 'temperature=0 is hard-wired in the provider, not left to callers.' S1/S7 put temperature on RunConfig/Settings and pass it through; S1's ClaudeLLM 'pins to config.temperature (0.0 for fair runs)' implying callers CAN set it. If the provider hard-wires 0 (S2) but RunConfig carries temperature (S1/S7) and the cassette key hashes temperature (S1/S2/S3/S7), a config temperature != 0 silently produces a cassette key that never matches the hard-wired-0 recording.
- MAX_TOKENS — S1/S2 pin max_tokens=256 in the provider; S5's cassette key includes max_tokens but the harness never sets it; S7 puts max_tokens=256 on Settings. If any scenario needs longer output (S3 research synthesis, S2 code patches produce diffs), 256 truncates and stop_reason='max_tokens', but the fairness contract and cost accounting assume it's a constant. A truncated blackboard narration vs a truncated orchestrator narration is not a fair token comparison.
- OTel input_tokens INCLUSIVE vs EXCLUSIVE — S2 explicitly maps gen_ai.usage.input_tokens = prompt_tokens (INCLUSIVE of cache, per OTel semconv) and keeps raw input_tokens exclusive. S3's llm_call_finished emits gen_ai.usage.input_tokens = 214 alongside gen_ai.usage.cache_read.input_tokens = 1800 — here input_tokens is EXCLUSIVE (Anthropic-native). S5's OTel span sets gen_ai.usage.input_tokens = u.total_input (INCLUSIVE). So the same OTel attribute name carries inclusive semantics in S2/S5 and exclusive in S3 — exporters will double- or under-count depending on which slice emitted the span.
- HYBRID DEFINITION — S1 hybrid delegates a 'sub-region of state' to a bounded BlackboardEngine and reintegrates via apply_patch. S5 hybrid 'fans out S3-style independent research (orchestrator-style, asyncio.gather), THEN for each candidate calls blackboard.run as a subroutine' — a fundamentally different shape (research-then-reconcile) than S1's (trunk-then-delegated-cluster). The two hybrids solve different scenarios and expose different configs (S1: delegated_agents/delegated_fields; S5: inner_max_steps/outer_max_rounds).

### Gaps identified
- CONCURRENCY/DETERMINISM (S1): The claim 'concurrency changes wall_ms, never the committed event order' is only true if every gathered coroutine reads the SAME pre-batch snapshot AND commits are pure. But agents read `view` at act() time. In S1's blackboard, the frontier is gathered concurrently against a snapshot taken before the batch, then committed sorted by registry index with a gate-check that can early-exit mid-batch. Coroutines whose commits are skipped by the early-exit have still consumed real tokens/latency (the LLM call already happened) yet may not appear as committed calls — the design never says whether gathered-but-uncommitted calls are billed. This is a real accounting hole: you either bill work you discarded or you discard tokens you spent.
- DETERMINISM WITH REAL LLMs (all slices): temp=0 + cassette makes REPLAY deterministic, but the N-run variance harness (S2/S5/S8) runs FRESH non-cassette calls to characterize nondeterminism. Nothing pins the ORDER of async completion in those fresh runs. S1 says commit order is registry-index-sorted so order is stable, but the SET of calls that occur can differ run-to-run in the blackboard because a gate early-exit inside a gathered batch depends on which fields changed, which under real (non-rule-pinned narration) is fine but under any future tool-use path (S1 ToolExecutor) is not. No slice states how tool-use round-trips (variable token counts, variable latency) interact with the 'structural metrics are ~zero variance' claim.
- STATE-SCHEMA EVOLUTION / CASSETTE VERSIONING: S7 versions cassettes under cassettes/v1 with a MANIFEST sha256, but the cassette KEY in every slice hashes (system, prompt) which embed the state dict repr / PlanState fields. If PlanState adds a field (S1's whole extensibility story), every prompt string changes, every cassette key changes, and ALL committed cassettes miss -> CassetteMiss hard-fail in CI. There is no migration/repricing story for schema drift beyond S2's --reprice (which only covers pricing, not prompt shape). The 'add a scenario = new domain package' extensibility claim collides with 'a missing digest is a hard error.'
- BACKPRESSURE (S3): The ring-buffer-overflow -> close-SSE -> client-gap-fills-from-JSONL design assumes the JSONL file sink keeps up with the engine at all times. In mock/replay mode the engine can emit thousands of events faster than fsync; there is no bound on JSONL write latency and no flow control between the engine and the durable sink. If the durable sink itself lags, the 'file is the relief valve' invariant breaks. Also, gap-fill by re-reading log.jsonl from ?from=seq requires the server to hold or re-open the file per reconnect; no story for log rotation/size caps on long runs.
- SECURITY / BLAST-RADIUS MATH (S5/S6): The amplification-factor claim rests on the ACTUAL subscription graph, which I verified: field 'scope' -> [Budget, Timeline, Risk]. A poisoned scope wakes 3 agents, but Budget owns max_scope which wakes Scope (a back-edge), so the real cascade is deeper than '3'. S6's PoisonAgent writes 'scope=-999'; but Scope's rule only fires on max_scope changes, and the gate/rules will immediately re-clamp — the demo may show a SMALLER amplification than claimed because the deterministic rules dampen the poison. The blast-radius number is emergent (good) but no slice validates it actually exceeds the orchestrator's by the asserted margin against THIS graph.
- RETRY/IDEMPOTENCY vs STREAMING USAGE (S2/S6): with_retry wraps llm.complete; on a mid-stream 529 after message_start but before message_stop, partial usage has been read (input buckets set, output=priming count). Retry re-issues the whole request and re-reads usage. No slice specifies that partial-stream usage from the failed attempt is discarded — if the CallRecord/cost governor charged on the partial, retries double-charge the budget. The Budget.charge / governor.check placement relative to retry is unspecified.
- PROMPT-CACHE RATE-LIMIT INTERACTION (S2/S6): S6 correctly notes cache reads still count against rate limits (rate_limited_input_tokens includes cache_read + cache_write). But S2's RateLimiter.acquire(est_input_tokens) is called BEFORE the request, when cache hit/miss is unknown, so the token-bucket estimate cannot know whether tokens will be billed as cache_read. Under-estimating causes 429 storms; over-estimating throttles unnecessarily. No slice reconciles pre-call token estimation with post-call cache accounting for the tpm bucket.
- HYBRID WORM ORDERING (S1): rec.child(span=...) writes into 'the SAME totally-ordered WORM log with a parent seq range,' and seq.reintegrate commits sub-writes. But the sub-blackboard runs its own Sequencer (its run() creates `seq = Sequencer()`). Two independent Sequencers cannot produce one gap-free monotonic seq. S3's hard invariant is 'seq is per-run, gap-free, uint, starts at 0' and the SSE client asserts seq==last+1. The hybrid's nested sub-run breaks gap-free monotonicity unless the parent injects its Sequencer, which S1's Engine.run signature does not pass down.
- MOCK-MODE FAIRNESS LEAK: In mock mode MockLLM returns usage = estimate_tokens(system+prompt). The blackboard's shared-state prompts embed the FULL state dict every call; as state fills in, prompt length grows, so later blackboard calls cost MORE tokens than early orchestrator calls on the same agent. The headline 'token' margin in mock mode is partly an artifact of prompt-length-from-state-fill, not topology. S8's insights.md waterfall ('blackboard's bigger prompts') acknowledges this for REAL mode but the committed golden mock numbers (511 vs 908) that CI pins are subject to the same effect and are treated as ground truth.
- NO CONCURRENCY LIMIT / RATE-LIMIT vs GATHER (S1): asyncio.gather over the frontier issues N concurrent Anthropic calls with no semaphore. With the RateLimiter (S2) being a blocking token-bucket, gather will either serialize inside acquire() (killing the parallelism that is the entire point of the blackboard's wall_ms advantage) or exceed rpm and trigger 429 backoff (adding latency the orchestrator doesn't pay). Either way the 'blackboard wall_ms < orchestrator' claim is unproven under real rate limits; no slice sizes the concurrency vs rpm relationship.
- SSE SINGLE-WRITER ASSUMPTION (S3/S4): S3 uses stdlib http.server+asyncio; S4/S7 use FastAPI+uvicorn. Neither addresses multiple concurrent SSE clients tailing a LIVE run: each needs its own ring buffer fed from one producer, and the producer must fan out without blocking on the slowest client. The design has per-connection RingBufferSink but the EventBus sinks list is constructed once at run start (bus = EventBus(..., sinks=[...])), so a client connecting mid-run isn't in the sinks list and only gets JSONL replay, never live tail — the 'tails live' promise fails for late joiners.
- GATE PROJECTION UNDEFINED (S1 hybrid): sub_gate = gate.project(config.delegated_fields) must return a Gate over a SUBSET of fields, but task.is_consistent references scope, budget_k, max_scope, timeline_weeks, risk together (e.g. timeline_weeks == scope*2). Projecting onto {budget_k,max_scope,timeline_weeks,risk} while scope is a 'trunk' field held constant is not a well-defined sub-consistency check — the projected gate can never be satisfied independently because its predicates reference the excluded scope. No slice defines projection semantics for cross-field predicates.

### Must-add for credibility (incorporated)
- A SINGLE canonical Usage dataclass and cassette-key spec, defined ONCE in a shared contract doc, that every slice imports rather than re-declares. Pick the 4-field Anthropic-native set {input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens} OR the 5-field 5m/1h split, and state explicitly whether input_tokens is inclusive or exclusive of cache, with the OTel mapping written once. The cassette key must be one formula with a documented canonicalization (which fields, whether temperature/seed/max_tokens/cache_mode are in it) and a schema_version prefix so a key format change is detectable, not a silent miss.
- A resolved, written-down prompt-caching fairness policy. It cannot be 'enabled and unbiased' (S1), 'off by default, biases orchestrator' (S2), and 'biases blackboard' (S5) simultaneously. Decide: headline margin on cache-OFF fair_tokens; caching as a separate labeled axis; and prove empirically (not assert) which topology the cache favors against the actual prompt-prefix structure. Document the directionality with a recorded measurement.
- A definitive Engine protocol (one signature, sync-or-async decided) and one EngineResult/RunResult/FinalState type. Reconcile S1's async injected-dependency form with S5's Scenario form and S7's registry form. The Scenario abstraction (S5) and the injected registry/gate/state (S1) must be unified — a Scenario should PRODUCE the injected registry/gate/initial, not be a parallel API.
- A single unified event envelope (S3 vs S4 are byte-incompatible: v string vs int, attributes{} vs data{}, type vs kind). One shape, one version field, one nesting convention, consumed identically by the CLI, the S3 stdlib SSE server, and the S4 FastAPI server. Also decide ONE SSE stack (stdlib http.server in S3 vs FastAPI in S4/S7) — shipping both is drift.
- A worked, VERIFIED convergence trace for the redesigned async blackboard proving it still yields 7 calls / 0 wasted (or updating every downstream golden/doc/money-shot number if it does not). Right now the frontier-gather redesign produces 9 calls in simulation; either fix the scheduler to preserve seed semantics (commit-then-ripple sequentially, gather only truly-independent agents that read post-commit state) or re-baseline S8's golden report.json, S4's ~511 bar, and the README headline.
- A single Sequencer that (a) keeps call-seq and write-event-seq as independent monotonic streams (the seed's _seq/_eseq split, which the S1 redesign merges and corrupts), and (b) is threaded through the hybrid's sub-run so nested spans share ONE gap-free per-run seq (required by S3's seq==last+1 client invariant). The current S1 hybrid creates a second Sequencer in the sub-run, breaking gap-freeness.
- Explicit async concurrency-vs-rate-limit design: a semaphore bounding gather() width, a statement of how the token-bucket RateLimiter interacts with concurrent acquire() (does it serialize the fan-out and erase the wall_ms advantage?), and a measured claim that blackboard wall_ms < orchestrator wall_ms UNDER the real rpm/tpm limits — not just under unlimited concurrency.
- A defined gate.project() semantics for cross-field predicates (S1 hybrid), or drop projected sub-gates. task.is_consistent couples scope to timeline_weeks/risk; projecting onto a field subset that excludes scope yields an unsatisfiable-or-trivial sub-gate. Specify how a predicate referencing an excluded field is handled (held-constant substitution vs error).
- A retry/usage-accounting spec: on mid-stream failure + retry, partial-stream usage MUST be discarded before the successful attempt's usage is charged, or the budget double-counts. State where Budget.charge/governor.check sit relative to with_retry and that only terminal (message_stop) usage is billed.
- A late-joiner SSE story: the S3 EventBus builds its sinks list once at run start, so a browser connecting mid-run gets only JSONL replay and never the live tail. Add per-connection sink registration against a live run, or state that live tail requires connecting before run start (and that all demos do so).
- Cassette schema-evolution handling: because keys hash the prompt which embeds PlanState fields, adding a state field invalidates every cassette (CassetteMiss hard-fail). Ship a migration/re-record path and make schema_version part of the manifest AND the key, so drift is a clear 'record needed' signal rather than a cryptic miss. Reconcile with S1's 'add a domain package' extensibility promise.

### Fairness / real-calling risks to watch
- QUIET FAIRNESS VIOLATION (caching, S1): S1 enables prompt caching with cache_control on the shared preamble and asserts 'cache_read savings accrue equally.' They do NOT accrue equally: cache hits depend on prompt-PREFIX STABILITY, and the two topologies template prompts differently (orchestrator re-issues near-identical fixed-order prompts; blackboard's reactive order has a colder prefix). S2 identifies exactly this as crediting the orchestrator for plumbing. S1's 'enabled and unbiased' stance is the fairness violation S2 warns about, shipped by default in the core.
- QUIET FAIRNESS VIOLATION (early-exit asymmetry): The seed blackboard checks the gate after EVERY commit and breaks; the seed orchestrator only breaks on a whole-sweep no-op. S5 correctly ships --orch-early-exit to give the orchestrator the SAME between-step gate check and requires the blackboard win to survive it. But S1's core blackboard bakes gate-after-each-commit into the engine while S1's orchestrator only checks 'if gate(state) or not changed: break' at end-of-round — so in the CORE (S1), the orchestrator does NOT get the per-step early exit that S5 insists on. The core engines as written re-introduce the exact asymmetry S5's fairness test is designed to catch.
- REALNESS EROSION (rule-as-decision-authority): Every slice keeps 'the rule is the decision authority; the LLM only narrates.' This means the REAL token/latency numbers are real but the CONTROL FLOW (which agent changes what, convergence path) is 100% deterministic regardless of model output. The comparison measures topology overhead on a FIXED decision trace, not real multi-agent behavior. That's defensible IF stated loudly, but S4's 'the frontend cannot tell live from replay -> provably honest' and S8's 'no number is hardcoded' overstate it: the DECISIONS are hardcoded (in rules), only the tokenization of narration is real. A senior reviewer will call this a narration benchmark, not an agent benchmark.
- REALNESS GAP (tool-use path): S1 introduces ToolSpec/ToolExecutor for 'real external data through a real tool-use round-trip,' but no scenario except S2 (pytest) and S3 (WebSearch) actually uses tools, and the flagship S1 reconciliation task's numbers come entirely from rules with zero tool calls. The 'real tokens from real tools' claim is unexercised on the headline scenario.
- FAIRNESS (max_tokens truncation): a global max_tokens=256 (S1/S2/S7) means any scenario whose narration or output exceeds it truncates with stop_reason=max_tokens. If the blackboard's larger shared-state prompts push its narration to truncate while the orchestrator's isolated prompts don't (or vice-versa), the output-token comparison is confounded by truncation, not topology.
- MOCK-MODE HEADLINE (511 vs 908) is partly a prompt-length artifact: MockLLM tokens = len(system+prompt)/4, and the blackboard embeds the growing state dict each call. The committed golden number CI pins therefore partly measures 'prompt grows as state fills,' not pure call-count difference. Since S8 treats the mock number as canonical ground truth and only shows real numbers as a caveat, the flagship headline a skeptic sees first is the confounded one.

## 12. Risk register
| Risk | Severity | Mitigation |
|---|---|---|
| Async blackboard scheduler changes the headline (frontier-gather-against-stale-snapshot → 9 calls, not 7) | **Critical** | Phase-0 gate: preserve seed FIFO commit-then-ripple-then-gate semantics; gather ONLY truly-independent agents reading post-commit state. A test pins 7/511 or every downstream golden is re-baselined in the same PR. |
| Five `Usage` schemas / six cassette keys ship simultaneously → cross-slice deserialization failures & CassetteMiss storms | **Critical** | ONE `contracts.py` imported everywhere; a lint/test asserts a single `class Usage` and single key formula; `ovbkey/N` version prefix. |
| Prompt-caching quietly credits one topology (the exact fairness violation) | High | Headline on `fair_tokens`, `cache_mode=off`; caching is a separate labeled axis; directionality measured & documented, not asserted. |
| Cache schema-drift: adding a `PlanState` field invalidates every cassette (hard-fail) collides with "add a domain package" extensibility | High | `cassettes/v{N}` + `state_schema_version` in MANIFEST; stale schema → explicit "run `ovb record`" error; new scenario ships its cassette (CONTRIBUTING). |
| Hybrid sub-run creates a 2nd Sequencer → breaks gap-free `seq`, SSE client asserts `seq==last+1` and stalls | High | Parent injects its Sequencer into the sub-run; `test_events.py` asserts gap-free monotonicity across nested spans. |
| Retry after mid-stream 529 double-charges budget (partial usage already read) | High | Only terminal `message_stop` usage is billed; `Budget.charge`/`governor.check` sit AFTER `with_retry`; partial-attempt usage discarded (spec'd in CONTRACTS). |
| Rate-limiter serializes `gather()` → erases the blackboard wall_ms advantage under real rpm | High | `asyncio.Semaphore` sizes concurrency to rpm; wall_ms advantage is a *measured* claim under real limits (Phase-1 exit), not assumed under unlimited concurrency. |
| Mock headline (511 vs 908) is partly a prompt-length-from-state-fill artifact, not pure topology | Medium | Report structural metrics (calls/wasted, ~zero variance) as the primary headline; document the token confound in `insights.md` for BOTH mock and real; lead with call-count, not raw tokens. |
| `gate.project()` on cross-field predicates (scope coupled to timeline) is unsatisfiable/trivial | Medium | Documented held-constant substitution: trunk fields are bound to current values inside the projected predicate; specified in CONTRACTS, tested. |
| `max_tokens=256` truncates longer scenarios (S2 diffs, S3 synthesis) → unfair token comparison | Medium | `max_tokens` is per-scenario config (in the cassette key); `stop_reason=max_tokens` surfaced loudly; fairness contract asserts equal max_tokens across engines for a scenario. |
| "Rule is decision authority; LLM only narrates" → a narration benchmark, not an agent benchmark | Medium | State loudly in methodology.md/faq.md; separate STRUCTURAL metrics (real topology overhead) from LLM metrics (real narration tokens); don't overstate "no number is hardcoded" — decisions are rule-fixed, tokenization is real. |
| Two SSE stacks (stdlib vs FastAPI) shipped = drift | Medium | ONE stack: FastAPI + sse-starlette; stdlib server dropped. |
| Real LLM nondeterminism makes single-run claims flimsy | Medium | temp=0 + N=20 fresh runs for variance; report median+IQR+min/max; margin only claimed when paired-diff bootstrap CI excludes zero. |
