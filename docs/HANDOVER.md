# ovb — Handover & project memory

_Last updated: 2026-07-02 · repo is **local-only** (not pushed) · latest commit `fe4f69c`._

This is the "pick it up cold" doc: what the project is, how to run it, how it's built,
what's done, what's next, and the gotchas. For the concept read [HARNESS.md](HARNESS.md);
for the full build plan read [PLAN.md](PLAN.md).

---

## 1. What it is

`ovb` (Orchestrator-vs-Blackboard) is a runnable, instrumented lab that runs the **same
agents** on the **same task** through **three control models** and measures the difference
(agent calls, tokens, real $ cost, latency, a WORM audit log).

Thesis: a multi-agent system = **agents + a harness**. The harness is the deterministic
control loop around the model. **Orchestrator, blackboard, and hybrid are three harnesses**;
only the *scheduling* differs. On an interdependent task the blackboard/hybrid converge in
fewer calls because a change re-triggers only the affected agents instead of re-sweeping all.

Headline (mock, deterministic): **orchestrator 12 calls · blackboard 7 · hybrid 5**, all
reaching the *identical* plan.

**Wording rule (important):** the orchestrator has **no shared board and no re-triggering**
— its state is supervisor-held, updated by fixed-order sweeps. Only the blackboard (and the
hybrid's core) has a shared board. Do NOT say the orchestrator has "shared memory". (At the
code level all three share one `PlanState` via `harness.invoke`; the real difference is
*scheduling*, not literal memory.)

## 2. Current state — what's built (v0.2)

- **src-layout package** `src/ovb/`, editable-installed (`pip install -e .`), `uv`-ready.
- **Typed kernel**: `PlanState` (pydantic, frozen) + ownership-checking reducer; `KnowledgeSource`
  agents; deterministic `Gate`; `Sequencer`; canonical `Usage`/`Event`/`Engine` contracts.
- **The Harness** (`core/harness.py`): shared control-loop step `invoke()` + `gate_passed()`.
  The three engines subclass it and implement ONLY `run()` (scheduling).
- **Three engines**: `orchestrator.py`, `blackboard.py`, `hybrid.py`.
- **Real LLM**: async streaming `ClaudeLLM` (correct cumulative-delta, cache-aware usage;
  `temperature` NOT sent — reasoning models deprecate it). `CassetteLLM` record/replay.
- **Pricing** (`pricing.py`, dated 2026-07-01): Haiku 4.5 $1/$5 (**default/cheapest**),
  Sonnet 5 $2/$10 (intro), Opus 4.8 $5/$25, Fable 5 $10/$50.
- **CLI** (`ovb ...`): `serve`, `bench`, `run`, `models`, `doctor`.
- **Live dashboard** (`viz/live.py`, stdlib SSE, no build step) — see §4.
- **Cassette** `cassettes/demo.json`: real recorded calls for 3 models (Haiku/Sonnet5/Opus) at guests=15/budget=600.
- **Docs**: HARNESS, WHEN-TO-USE, EXAMPLE, PLAN, RESEARCH, architecture, this handover.
- **Tests**: `tests/` (10 pass, deterministic, no network).

## 3. Quickstart

```bash
pip install -e ".[dev]"            # or: export PYTHONPATH=src
ovb serve                          # ⭐ the dashboard (browser). Add --lan to share on your network.
ovb bench                          # 3 harnesses, mock, comparison + output/report.html
ovb models                         # compare Haiku/Sonnet/Opus/Fable — same result, different cost
ovb run blackboard                 # one harness, print its trace
ovb doctor                         # what mode am I in?
make test                          # pytest
```

## 4. The UI — story journey (`/`) + expert dashboard (`/expert`)

**The default UI is now a 4-scene, gamified story in A2-simple English** (built 2026-07-02
per the IMPROVEMENTS plan + owner's "full immersive experience" ask). It lives in real
files — `src/ovb/viz/static/{index.html,style.css,app.js}` — served by the same stdlib
server (routes `/`, `/static/*`, `/expert`, `/info`, `/run`). Scenes: ① animated problem
intro (budget bar overflow) → ② the three "ways" with looping mini-diagrams + a
make-your-guess game → ③ the race: three lanes, traveling dots on arrows, client-side
buffered playback (per-engine queues drained **round-robin** so lanes race together;
pause/step/speed presets) → ④ winner podium + medals + confetti + guess payoff + score
table. Solo mode ("watch only this way") works from scene 2. `ovb export` inlines
everything + the event stream into a self-contained `examples/demo.html` (replays with
no server — `window.PRELOADED` branch in app.js).

## 4b. The expert dashboard (`ovb serve` → /expert)

Runs all three harnesses **concurrently** over the same prompt, streaming every event live.
- **Problem card** with an **ELI5 ⇄ Expert** toggle (plain "four teammates" story vs precise
  mechanics), three color-coded "ways" mini-cards, and a live **expected-plan target**.
- **Per engine**: an animated **flow diagram** (Supervisor/Board nodes, arrows that light up
  per step — message=blue, write=teal, re-trigger=purple), the **state board**, **agent talk**
  (real model narration, clamped with "show more"), a plain-language **play-by-play** log, and
  live meters (calls, wasted, tokens, $, gate).
- **Comparison table** under the panels (calls/wasted/writes/tokens/cost/steps/plan/gate + margins).
- **Compare** all three or **focus** one; **Glossary** tab; **light/dark** toggle (persisted).
- **Modes**: Mock (fake, instant, offline), Cassette (replay recorded REAL calls offline, no key),
  Real API (live streaming Claude — needs key, costs $). Model picker defaults to cheapest (Haiku).
- Auto-run URL params for shareable links: `/?auto=1&mode=cassette&delay=0`.

## 5. Sharing the dashboard

- **`ovb serve --lan`** → binds `0.0.0.0`, prints `http://<LAN-IP>:<port>/`. Anyone on the same
  Wi-Fi/VPN can open it. **No tunnel, nothing leaves the network** — the reliable option on a
  **managed/corporate Mac** where endpoint security (Jamf Protect, Netskope DLP) blocks tunnels.
- **`ovb serve --ngrok`** → public URL via the ngrok CLI (needs `NGROK_AUTHTOKEN` in `.env`).
  Often **blocked/quarantined on managed Macs** and may be against DLP policy — prefer `--lan`.
  Degrades gracefully (serves locally) if ngrok is missing/blocked.

## 6. Real API, cassettes, secrets

- **`.env`** (gitignored, never commit): `ANTHROPIC_API_KEY=...` and `NGROK_AUTHTOKEN=...`.
  Loaded by a stdlib `dotenv.py`.
- **⚠️ ROTATE the Anthropic API key** — it was pasted into a chat transcript. The repo never
  stored it (only `.env`, gitignored; verified no key in git history).
- **Cassettes**: `ovb bench --real --cassette cassettes/demo.json` records; without `--real` it
  replays offline (real tokens/cost, no key). Keyed by canonical request hash → **changing the
  task/prompt = cassette miss → must re-record** (real calls, small cost).

## 7. Architecture map

```
contracts.py   canonical Usage / Event / Sequencer / Engine (one source of truth)
config.py      RunConfig (model, temperature, step_delay — fairness-critical, pinned)
pricing.py     dated Claude list prices → real $ cost
core/harness.py  Harness base: invoke() (one control-loop step) + gate_passed()
core/state.py    PlanState (frozen) + apply_patch ownership reducer
core/registry.py KnowledgeSource (agent) + subscription index
core/gate.py     PredicateGate (deterministic done-check)
core/llm.py      MockLLM · ClaudeLLM (streaming) · CassetteLLM (record/replay)
core/trace.py    Recorder + WORM event stream (OTel gen_ai.* aligned) + live on_event sink
engines/         orchestrator.py · blackboard.py · hybrid.py   (scheduling ONLY)
domain/          task.py (scenario + gate) · agents.py (the 4 specialists)
eval/            runner.py (build world once) · compare.py (FairnessContract + table)
viz/             report.py (static animated HTML) · live.py (stdlib SSE dashboard)
cli.py           ovb serve|bench|run|models|doctor
```
Fairness is enforced in code: everything except `run()` is shared; `FairnessContract`
hard-fails if roster/gate/sampling/start differ or engines diverge on the final plan.

## 8. The demo task & how to change it

Current task = **birthday party** (`domain/task.py`): agents **Guests, Budget, Food,
Chairs** reconcile `guests/max_guests/cost/pizzas/chairs` to a fixpoint (defaults →
12 guests · $600 · 4 pizzas · 12 chairs). It's interdependent (budget caps the guest
list → pizzas & chairs re-check; $50/head is ALL-IN, pizzas = shopping list 1-per-3,
chairs = 1 per guest — all physically countable), which is what makes the blackboard
win. Guests↔Budget is the coupled core; Food/Chairs the tail. Chairs replaced the
earlier "Vibe" agent because a feeling wasn't countable — the dependency never clicked.

**To swap the task** (e.g. another domain), touch:
1. `domain/task.py` — `ScenarioParams`, constants, `initial_state`, `is_consistent` (the gate),
   `chairs_for`/`pizzas_for`, `scenario_text`.
2. `domain/agents.py` — agent names, `owns`/`subscribes`, `rule` functions.
3. `core/state.py` — `PlanState` fields.
4. `tests/test_smoke.py` — `EXPECTED` final state + headline call counts.
5. UI (`viz/live.py`) — `FIELDS`, `AGENTC`, board/flow node labels, the ELI5 copy, glossary,
   and the JS `recalcTarget()` (mirrors task.py math).
6. **Re-record cassettes** for the new prompts (real API), or the dashboard's Cassette mode misses.
Keep the interdependence (a change must ripple to a *subset* of agents) or the blackboard's
advantage disappears.

## 9. Testing

`make test` / `python -m pytest -q` → 10 tests (mock, deterministic, no network): three-way
convergence to the same plan, headline call counts (12/7/5), fairness contract, ownership
reducer, the live SSE pump (event completeness, re-triggers, agent talk).

## 10. Roadmap — done vs TODO

Done: kernel, 3 engines, harness concept, real streaming + cassettes, 4-model cost comparison,
live dashboard (flow anim, ELI5/Expert, comparison table, themes, glossary, modes), LAN/ngrok,
two adversarial audits (~20 bugs fixed), cited SOTA research.

TODO: (a) **make the demo task more concrete/relatable** (in discussion — options being chosen);
(b) an **orchestrator-WINS scenario** (a clean routing/fan-out task) so the catalog is balanced;
(c) more scenarios (real-pytest debug, real-search synthesis); (d) N-run bootstrap-CI harness for
real-mode variance; (e) security blast-radius harness (poisoned-board amplification); (f) self-
syncing docs/RESULTS from benchmark JSON; (g) optional FastAPI+React/D3 dashboard (the stdlib one
is a complete stand-in); (h) push to GitHub.

## 11. Gotchas & key decisions

- **temperature** is deprecated on reasoning models (claude-sonnet-5) → `ClaudeLLM` must not send it.
- **Model choice never changes the result** (plan/call counts) — only narration tokens/cost —
  because decisions are rule-based and the model only narrates. Default to the cheapest (Haiku).
- **Streaming, not Batch.** The Batch API is 50% cheaper but async (24h) and can't stream — wrong
  for a live UI. We use the streaming Messages API.
- **Managed macOS**: Jamf Protect + Netskope DLP + Elastic Agent are present and org-locked →
  ngrok is likely blocked; prefer `--lan`.
- **Sandbox testing quirks** (for whoever automates via Claude Code): the `preview_click` MCP tool
  doesn't dispatch to page `onclick` handlers — drive via `preview_eval` (`run()` / `element.click()`).
  Network needs the sandbox disabled, but the homebrew `ngrok` binary isn't executable in that mode
  — so the live ngrok tunnel can't be validated in-sandbox (it works in a real terminal).
- **Dashboard is stdlib** (ThreadingHTTPServer + hand-rolled SSE) on purpose: clone-and-run, no deps,
  no build. Streamlit was rejected (it re-runs the whole script and can't stream frame-by-frame).
