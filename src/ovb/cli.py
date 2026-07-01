"""`ovb` command line — the front door.

    ovb bench                         # all 3 harnesses, mock, comparison + HTML
    ovb bench --features 10 --budget 75   # same "prompt" (params) to all three
    ovb bench --real                  # live Claude calls (needs ANTHROPIC_API_KEY)
    ovb bench --cassette cassettes/demo.json  # replay recorded real calls offline
    ovb run blackboard                # one harness, print its trace
    ovb serve                         # LIVE side-by-side dashboard (real-time, full visibility)
    ovb doctor                        # what mode am I in?
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from .config import RunConfig
from .dotenv import load_dotenv
from .domain import agents, task
from .domain.task import ScenarioParams
from .eval.compare import FairnessContract, render_comparison
from .eval.runner import build_gate, run_all, run_engine
from .viz import render_html

load_dotenv()  # pick up ANTHROPIC_API_KEY from a local .env for --real

app = typer.Typer(add_completion=False,
                  help="Orchestrator vs Blackboard vs Hybrid — harness topologies, measured.")


def _params(features: int, budget: int) -> ScenarioParams:
    return ScenarioParams(requested_features=features, budget_cap_k=budget)


def _trace(result) -> str:
    rec = result.recorder
    out = [f"── {rec.control_model.upper()} ──"]
    for c in rec.calls:
        writes = ", ".join(f"{k}={v[1]}" for k, v in c.writes.items()) or "(no change)"
        mark = "*" if c.changed else " "
        out.append(f"  {c.seq:>2}{mark} {c.agent:<9} [{c.trigger:<22}] "
                   f"{writes:<26} {c.usage.total:>4}tok  ${c.cost_usd:.5f}")
    out.append(f"  final: {result.state}  consistent={result.consistent}")
    return "\n".join(out)


@app.command()
def bench(
    features: int = typer.Option(8, help="requested features (the shared 'prompt')"),
    budget: int = typer.Option(90, help="budget cap $k"),
    real: bool = typer.Option(False, help="live Anthropic calls"),
    model: str = typer.Option("claude-sonnet-5"),
    cassette: str = typer.Option(None, help="record/replay path"),
    orch_early_exit: bool = typer.Option(False, help="give orchestrator the same gate early-exit"),
    html: str = typer.Option("output/report.html", help="animated report path ('' to skip)"),
):
    """Run all three harnesses on the same task and compare."""
    config = RunConfig(real=real, model=model, cassette=cassette,
                       orch_early_exit=orch_early_exit)
    params = _params(features, budget)
    results = asyncio.run(run_all(config, params))

    FairnessContract.assert_comparable(
        results, registry=agents.build_registry(params), gate=build_gate(params),
        config=config,
    )
    typer.echo(task.scenario_text(params) + "\n")
    for r in results.values():
        typer.echo(_trace(r) + "\n")
    typer.echo(render_comparison(results))

    for name, r in results.items():
        r.recorder.write_jsonl(f"output/{name}.jsonl")
    if html:
        Path(html).parent.mkdir(parents=True, exist_ok=True)
        Path(html).write_text(render_html(results, task.scenario_text(params)))
        typer.echo(f"\n  HTML report → {html}")
        typer.echo("  event logs  → output/*.jsonl")


@app.command()
def run(engine: str = typer.Argument(..., help="orchestrator|blackboard|hybrid"),
        features: int = typer.Option(8), budget: int = typer.Option(90),
        real: bool = typer.Option(False), model: str = typer.Option("claude-sonnet-5"),
        cassette: str = typer.Option(None)):
    """Run a single harness and print its trace."""
    config = RunConfig(real=real, model=model, cassette=cassette)
    params = _params(features, budget)
    result = asyncio.run(run_engine(engine, config, params))
    typer.echo(task.scenario_text(params) + "\n")
    typer.echo(_trace(result))


@app.command()
def serve(host: str = typer.Option("127.0.0.1"), port: int = typer.Option(0, help="0 => $PORT or 8000"),
          open_browser: bool = typer.Option(True, help="open the dashboard in a browser")):
    """Launch the LIVE side-by-side dashboard (real-time, full visibility)."""
    import os
    if not port:
        port = int(os.environ.get("PORT", "8000"))
    from .viz.live import serve as _serve
    _serve(host=host, port=port, open_browser=open_browser)


@app.command()
def doctor():
    """Report the execution mode and dependency availability."""
    def have(m):
        try:
            __import__(m); return "yes"
        except ImportError:
            return "no"
    import os
    typer.echo("ovb doctor")
    typer.echo(f"  anthropic SDK (for --real): {have('anthropic')}")
    typer.echo(f"  ANTHROPIC_API_KEY set:      {'yes' if os.environ.get('ANTHROPIC_API_KEY') else 'no'}")
    typer.echo("  live dashboard (`ovb serve`): standard-library only, no extra deps")
    typer.echo("  default mode: MOCK (deterministic, offline) unless --real or --cassette")


if __name__ == "__main__":
    app()
