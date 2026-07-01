"""`ovb` command line — the front door.

    ovb bench                 # all 3 topologies, mock, print comparison + write HTML
    ovb bench --real          # live Claude calls (needs ANTHROPIC_API_KEY)
    ovb bench --cassette cassettes/s1.json   # replay recorded real calls offline
    ovb run blackboard        # one topology, print its trace
    ovb doctor                # what mode am I in, are deps present
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from .config import RunConfig
from .core.gate import PredicateGate
from .domain import agents, task
from .eval.compare import FairnessContract, render_comparison
from .eval.runner import run_all, run_engine
from .viz import render_html

app = typer.Typer(add_completion=False, help="Orchestrator vs Blackboard vs Hybrid — harness topologies, measured.")


def _cfg(real, model, cassette, orch_early_exit) -> RunConfig:
    return RunConfig(real=real, model=model, cassette=cassette,
                     orch_early_exit=orch_early_exit)


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
    real: bool = typer.Option(False, help="live Anthropic calls"),
    model: str = typer.Option("claude-sonnet-5"),
    cassette: str = typer.Option(None, help="record/replay path"),
    orch_early_exit: bool = typer.Option(False, help="give orchestrator the same gate early-exit"),
    html: str = typer.Option("output/report.html", help="animated report path ('' to skip)"),
):
    """Run all three harnesses on the same task and compare."""
    config = _cfg(real, model, cassette, orch_early_exit)
    results = asyncio.run(run_all(config))

    FairnessContract.assert_comparable(
        results, registry=agents.build_registry(),
        gate=PredicateGate(task.is_consistent, spec="reconcile.is_consistent/v1"),
        config=config,
    )
    typer.echo(task.SCENARIO + "\n")
    for r in results.values():
        typer.echo(_trace(r) + "\n")
    typer.echo(render_comparison(results))

    for name, r in results.items():
        r.recorder.write_jsonl(f"output/{name}.jsonl")
    if html:
        Path(html).parent.mkdir(parents=True, exist_ok=True)
        Path(html).write_text(render_html(results, task.SCENARIO))
        typer.echo(f"\n  HTML report → {html}")
        typer.echo(f"  event logs  → output/*.jsonl")


@app.command()
def run(engine: str = typer.Argument(..., help="orchestrator|blackboard|hybrid"),
        real: bool = typer.Option(False), model: str = typer.Option("claude-sonnet-5"),
        cassette: str = typer.Option(None)):
    """Run a single harness and print its trace."""
    config = _cfg(real, model, cassette, False)
    result = asyncio.run(run_engine(engine, config))
    typer.echo(task.SCENARIO + "\n")
    typer.echo(_trace(result))


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
    typer.echo(f"  fastapi (for `ovb serve`):  {have('fastapi')}")
    typer.echo("  default mode: MOCK (deterministic, offline) unless --real or --cassette")


if __name__ == "__main__":
    app()
