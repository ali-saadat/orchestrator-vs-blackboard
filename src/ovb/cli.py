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


def _params(ask: int, band: int) -> ScenarioParams:
    return ScenarioParams(ask0=ask, band_max=band)


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
    ask: int = typer.Option(130, help="candidate's opening salary ask, $k (the shared 'prompt')"),
    band: int = typer.Option(110, help="HR's hard salary band cap, $k"),
    real: bool = typer.Option(False, help="live Anthropic calls"),
    model: str = typer.Option("claude-haiku-4-5-20251001"),
    cassette: str = typer.Option(None, help="record/replay path"),
    orch_early_exit: bool = typer.Option(False, help="give orchestrator the same gate early-exit"),
    html: str = typer.Option("output/report.html", help="animated report path ('' to skip)"),
):
    """Run all three harnesses on the same task and compare."""
    config = RunConfig(real=real, model=model, cassette=cassette,
                       orch_early_exit=orch_early_exit)
    params = _params(ask, band)
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
        ask: int = typer.Option(130), band: int = typer.Option(110),
        real: bool = typer.Option(False), model: str = typer.Option("claude-haiku-4-5-20251001"),
        cassette: str = typer.Option(None)):
    """Run a single harness and print its trace."""
    config = RunConfig(real=real, model=model, cassette=cassette)
    params = _params(ask, band)
    result = asyncio.run(run_engine(engine, config, params))
    typer.echo(task.scenario_text(params) + "\n")
    typer.echo(_trace(result))


@app.command()
def models(
    ask: int = typer.Option(130), band: int = typer.Option(110),
    real: bool = typer.Option(False, help="live calls (else replay from cassette)"),
    cassette: str = typer.Option("cassettes/demo.json"),
    models: str = typer.Option(
        "claude-haiku-4-5-20251001,claude-sonnet-5,claude-opus-4-8",
        help="comma-separated model ids to compare (add claude-fable-5 to include Fable)"),
):
    """Compare models on the SAME task and flag what actually differs.

    Because agent decisions are rule-based, the plan and call counts are identical
    across models — only narration tokens and cost differ. This makes the cost of
    each model explicit so you can pick the cheapest that fits.
    """
    from .pricing import get_price, is_known
    model_ids = [m.strip() for m in models.split(",") if m.strip()]
    params = _params(ask, band)
    rows = []
    for m in model_ids:
        cfg = RunConfig(real=real, model=m, cassette=(None if real else cassette))
        try:
            res = asyncio.run(run_all(cfg, params))
        except Exception as exc:  # e.g. cassette miss for a model not recorded
            rows.append((m, None, str(exc)))
            continue
        rows.append((m, res, None))

    def _total_cost(res):
        return sum(res[e].recorder.total_cost_usd for e in ("orchestrator", "blackboard", "hybrid"))

    ok = [(m, res) for m, res, err in rows if err is None]
    cheapest = min(ok, key=lambda mr: _total_cost(mr[1]))[0] if ok else None

    typer.echo(task.scenario_text(params) + "\n")
    hdr = f"  {'MODEL':<30}{'$/Mtok in/out':>14}{'calls o/b/h':>13}{'tokens o/b/h':>20}{'cost o/b/h (USD)':>28}"
    typer.echo(hdr)
    typer.echo("  " + "-" * (len(hdr) - 2))
    plans = set()
    calls_sets = set()
    for m, res, err in rows:
        price = get_price(m)
        pr = f"{price.input_per_mtok:g}/{price.output_per_mtok:g}" if is_known(m) else "n/a"
        if err:
            typer.echo(f"  {m:<30}{pr:>14}   (not in cassette — record with --real)")
            continue
        o, b, h = res["orchestrator"].recorder, res["blackboard"].recorder, res["hybrid"].recorder
        calls = f"{o.n_calls}/{b.n_calls}/{h.n_calls}"
        toks = f"{o.total_usage.total}/{b.total_usage.total}/{h.total_usage.total}"
        cost = f"${o.total_cost_usd:.4f}/${b.total_cost_usd:.4f}/${h.total_cost_usd:.4f}"
        st = res["blackboard"].state
        plan = f"${st['salary']}k+{st['bonus']}k bonus·{st['remote']}d remote"
        plans.add(plan)
        calls_sets.add(calls)
        flag = " ★ cheapest" if m == cheapest else ""
        typer.echo(f"  {m:<30}{pr:>14}{calls:>13}{toks:>20}{cost:>28}{flag}")
        typer.echo(f"  {'':<30}{'':<14}→ plan: {plan}")

    typer.echo("")
    n_ok = len(ok)
    identical = n_ok >= 2 and len(plans) == 1 and len(calls_sets) == 1
    typer.echo(f"  → calls + final plan identical across {n_ok} model(s): {identical}"
               + ("  (decisions are rule-based)" if identical else "  (need ≥2 models to compare)"))
    if cheapest:
        cp = get_price(cheapest)
        typer.echo(f"  → only narration tokens/cost differ → cheapest here: {cheapest} "
                   f"(${cp.input_per_mtok:g}/${cp.output_per_mtok:g} per Mtok).")
    typer.echo("  → streaming Messages API (real-time), NOT the Batch API.")


@app.command()
def serve(host: str = typer.Option("127.0.0.1"), port: int = typer.Option(0, help="0 => $PORT or 8000"),
          open_browser: bool = typer.Option(True, help="open the dashboard in a browser"),
          lan: bool = typer.Option(False, help="serve on your LAN (0.0.0.0) so same-network devices can open it — corporate-safe, no tunnel"),
          ngrok: bool = typer.Option(False, help="expose a PUBLIC url via ngrok (needs NGROK_AUTHTOKEN; may be blocked on managed Macs — prefer --lan)")):
    """Launch the LIVE side-by-side dashboard (real-time, full visibility).

    Sharing: `--lan` (same network, no tunnel — reliable on managed/corporate Macs)
    or `--ngrok` (public URL — often blocked by endpoint security like Jamf/Netskope).
    """
    import os
    if not port:
        port = int(os.environ.get("PORT", "8000"))
    if lan:
        host = "0.0.0.0"   # serve on all interfaces; ngrok still reaches localhost:port
    from .viz.live import serve as _serve
    _serve(host=host, port=port, open_browser=open_browser, ngrok=ngrok)


@app.command()
def export(
    out: str = typer.Option("examples/demo.html", help="output file"),
    ask: int = typer.Option(130), band: int = typer.Option(110),
):
    """Build ONE self-contained demo.html — the full story journey replaying a
    recorded run with no server, no install (works from file:// or any static host)."""
    import json as _json
    from .viz.live import DEMO_CASSETTE, SCENARIO_ID, _STATIC_DIR

    params = _params(ask, band)
    use_cassette = Path(DEMO_CASSETTE).exists()
    config = RunConfig(cassette=(DEMO_CASSETTE if use_cassette else None))

    def _collect(cfg) -> dict[str, list]:
        out: dict[str, list] = {}
        for name in ("orchestrator", "blackboard", "hybrid"):
            events: list = []

            def sink(ev, _n=name, _evs=events):
                d = ev.model_dump()
                d["engine"] = _n
                _evs.append(d)

            asyncio.run(run_engine(name, cfg, params, event_sink=sink))
            out[name] = events
        return out

    try:
        per_engine = _collect(config)
    except Exception:
        # e.g. cassette miss for non-default guests/budget → fall back to mock
        use_cassette = False
        per_engine = _collect(RunConfig())

    # round-robin interleave so the three lanes appear to run together
    merged: list = [{"engine": "_meta", "kind": "start", "attrs": {}}]
    queues = [per_engine[n][:] for n in per_engine]
    while any(queues):
        for q in queues:
            if q:
                merged.append(q.pop(0))
    merged.append({"engine": "_meta", "kind": "all_done", "attrs": {}})

    html = (_STATIC_DIR / "index.html").read_text()
    css = (_STATIC_DIR / "style.css").read_text()
    js = (_STATIC_DIR / "app.js").read_text()
    preloaded = _json.dumps({
        "events": merged,
        "info": {"cassette": use_cassette, "defaults": {"ask": ask, "band": band},
                 "scenario": SCENARIO_ID},
    })
    html = html.replace('<link rel="stylesheet" href="/static/style.css">',
                        "<style>\n" + css + "\n</style>")
    html = html.replace('<script src="/static/app.js"></script>',
                        "<script>window.PRELOADED=" + preloaded + "</script>\n<script>\n"
                        + js + "\n</script>")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(html)
    typer.echo(f"self-contained demo → {out}  "
               f"({'recorded REAL calls' if use_cassette else 'mock narration'}, "
               f"{len(merged)} events, {Path(out).stat().st_size // 1024} KB)")


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
