# ovb — Orchestrator vs Blackboard vs Hybrid

**Watch three multi-agent control models solve the *same* task, side by side — and see
which one wastes the fewest agent calls.** A runnable, instrumented lab for anyone
deciding how to coordinate LLM agents.

Same agents, same task, same deterministic done-check. Only the **control loop** differs.
Everything is measured: agent calls, tokens, real $ cost, and a full audit log.

![Orchestrator vs Blackboard vs Hybrid](docs/images/topologies.svg)

---

## Run it — one click

```bash
git clone <this-repo> && cd ovb
./run.sh                 # opens the live dashboard in your browser
```

- **macOS:** or just **double-click `run.command`** in Finder.
- Also: `make run`, or `uv run ovb serve`, or `pip install -e . && ovb serve`.

**No API key needed.** The dashboard ships with **recorded real Claude calls** you can
replay offline (real tokens & cost, zero spend). `./run.sh` uses [`uv`](https://docs.astral.sh/uv/)
if present, otherwise it creates a local `.venv` on first run.

Share it on your network (no tunnel — works on managed/corporate Macs):

```bash
./run.sh --lan           # prints an http://<your-ip>:8000/ URL for the same Wi-Fi/VPN
```

## The demo: build a gaming PC that fits a budget

Four specialist agents agree on one build. Their choices are **interdependent**:

| Agent | Owns | Rule |
|---|---|---|
| **GPU** | the tier (you want 4) | drop the tier if the budget won't allow it |
| **Budget** | cost + the affordable tier | cost = tier × $300; cap $1000 ⇒ tier 3 max |
| **Power** | PSU watts | watts = tier × 150 + 100 |
| **Performance** | FPS class | follows the tier (4→ultra, 3→high, …) |

You want a tier-4 GPU, but it blows the $1000 budget — so it drops to tier 3, and the
wattage and FPS drop with it. All three control models reach the **same** build
(`tier 3 · $900 · 550W · high`); they differ only in how much coordination it takes:

```
              agent calls   wasted (no-op)   tokens (Haiku, real)
orchestrator       12             5                 2,988
blackboard          7             0                 1,863   ← 1.71× fewer calls
hybrid              5             0                 1,367
```

## The three control models (harnesses)

- **Orchestrator** — a supervisor calls each agent in a fixed order, looping until stable,
  plus a confirming no-op sweep. No shared board, no reactivity. The most turns ("hub tax").
- **Blackboard** — all agents read/write one shared board; a write re-triggers only the
  agents that depend on the changed field. Fewer wasted turns.
- **Hybrid** — a bounded blackboard for the tightly-coupled core (GPU ↔ Budget), then a
  linear supervisor tail (Power, Performance).

They're the **same agents** behind one **harness** (control loop); only the *scheduling*
differs — see [docs/HARNESS.md](docs/HARNESS.md).

## The live dashboard

`./run.sh` opens a browser dashboard that runs all three concurrently and streams every step:

- an **ELI5 ⇄ Expert** problem explainer, animated **flow diagrams** (arrows light up per
  step), the live **state board**, **agent talk**, a plain-language **play-by-play**, and a
  consolidated **comparison table** with honest margins;
- **compare** all three or **focus** one; a **Glossary** tab; **light/dark** toggle;
- **modes**: Mock (offline), **Cassette** (replay real recorded calls, no key), Real API
  (live streaming Claude); a **model picker** defaulting to the cheapest (Haiku 4.5).

## CLI

```bash
ovb serve                 # the live dashboard  (--lan to share, --ngrok for a public URL)
ovb bench                 # all 3 harnesses, mock, + a comparison + output/report.html
ovb models                # compare Haiku/Sonnet/Opus — same result, different cost
ovb run blackboard        # one harness, print its trace
ovb bench --real          # live Claude calls (needs ANTHROPIC_API_KEY in .env, and the
                          #   `real` extra: uv run --extra real ovb …  /  pip install -e '.[real]')
ovb doctor                # what mode am I in?
```

Because decisions are rule-based (the model only *narrates*), the model choice never
changes the build — only tokens/cost. So use the cheapest that fits. See
[docs/EXAMPLE.md](docs/EXAMPLE.md) for the real 3-model numbers.

## Project structure

```
run.sh · run.command       one-click launchers
pyproject.toml             package + deps (uv/pip); entry point: `ovb`
src/ovb/
  contracts.py             canonical Usage / Event / Engine types
  config.py · pricing.py   run config; dated Claude prices → real $
  core/                    harness.py (the control-loop primitives) · state · registry ·
                           gate · llm (mock/streaming/cassette) · trace (WORM log)
  engines/                 orchestrator · blackboard · hybrid   (scheduling only)
  domain/                  task.py (the PC-build scenario + gate) · agents.py
  eval/                    runner · compare (fairness contract + table)
  viz/                     report.py (static HTML) · live.py (dashboard)
  cli.py                   `ovb` command line
tests/                     deterministic, no network
cassettes/demo.json        recorded real Claude calls (replay offline)
docs/                      HARNESS · WHEN-TO-USE · EXAMPLE · HANDOVER · PLAN · RESEARCH · architecture
```

## Development

```bash
pip install -e ".[dev]"    # or: uv run --extra dev …
make test                  # pytest (deterministic, no network)
make bench                 # regenerate output/report.html
```

New to the code? Start with [docs/HANDOVER.md](docs/HANDOVER.md), then
[docs/HARNESS.md](docs/HARNESS.md).

## Documentation

- **[docs/HARNESS.md](docs/HARNESS.md)** — the harness concept + how the three topologies map to code.
- **[docs/WHEN-TO-USE.md](docs/WHEN-TO-USE.md)** — decision guide: which control model to pick.
- **[docs/EXAMPLE.md](docs/EXAMPLE.md)** — real-Claude worked example (3 models), reproducible offline.
- **[docs/HANDOVER.md](docs/HANDOVER.md)** — cold-start handover & project state.
- **[docs/PLAN.md](docs/PLAN.md)** · **[docs/RESEARCH.md](docs/RESEARCH.md)** · **[docs/architecture.md](docs/architecture.md)**.

## License

MIT — see [LICENSE](LICENSE).
