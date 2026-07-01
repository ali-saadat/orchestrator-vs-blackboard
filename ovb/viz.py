"""Rendering: console trace + a self-contained HTML comparison report.

Nothing here computes results; it only formats whatever the recorders captured.
"""
from __future__ import annotations

import html


# ---- console --------------------------------------------------------------

def _fmt_state(state: dict) -> str:
    return (f"scope={state['scope']} max_scope={state['max_scope']} "
            f"budget=${state['budget_k']}k timeline={state['timeline_weeks']}w "
            f"risk={state['risk']}")


def render_trace(result: dict) -> str:
    rec = result["recorder"]
    lines = [f"── {rec.engine.upper()} ──"]
    for c in rec.calls:
        writes = ", ".join(f"{k}={v}" for k, v in c.writes.items()) or "(no change)"
        mark = "*" if c.changed else " "
        lines.append(
            f"  {c.seq:>2}{mark} {c.agent:<9} [{c.trigger:<14}] "
            f"{writes:<28} {c.usage.total:>4}tok"
        )
    lines.append(f"  final: {_fmt_state(result['state'])}")
    return "\n".join(lines)


def render_comparison(orch: dict, bb: dict) -> str:
    o, b = orch["recorder"], bb["recorder"]

    def row(label, ov, bv, better_low=True):
        try:
            ratio = (ov / bv) if bv else float("inf")
        except ZeroDivisionError:
            ratio = float("inf")
        win = "blackboard" if (ov > bv) == better_low else "orchestrator"
        if ov == bv:
            win = "tie"
        return f"  {label:<22} {str(ov):>14} {str(bv):>14}   {win}"

    ou, bu = o.total_usage, b.total_usage
    out = [
        "",
        "  METRIC                    ORCHESTRATOR      BLACKBOARD   advantage",
        "  " + "-" * 68,
        row("agent calls", o.n_calls, b.n_calls),
        row("  effective (changed)", o.n_effective, b.n_effective, better_low=False),
        row("  wasted (no-op)", o.n_wasted, b.n_wasted),
        row("state writes", o.n_writes, b.n_writes),
        row("prompt tokens", ou.prompt_tokens, bu.prompt_tokens),
        row("completion tokens", ou.completion_tokens, bu.completion_tokens),
        row("total tokens", ou.total, bu.total),
        row("sim latency (ms)", round(o.total_latency_ms, 1),
            round(b.total_latency_ms, 1)),
        "  " + "-" * 68,
    ]
    if b.n_calls:
        out.append(f"  → blackboard used {o.n_calls / b.n_calls:.2f}x fewer calls "
                   f"and {ou.total / max(bu.total, 1):.2f}x fewer tokens")
    same = orch["state"] == bb["state"]
    out.append(f"  → both reached the SAME consistent plan: {same}  "
               f"(orchestrator={orch['consistent']}, blackboard={bb['consistent']})")
    return "\n".join(out)


# ---- html -----------------------------------------------------------------

def _calls_html(rec) -> str:
    rows = []
    for c in rec.calls:
        writes = ", ".join(f"{k}={v}" for k, v in c.writes.items()) or "—"
        cls = "chg" if c.changed else "noop"
        rows.append(
            f"<tr class='{cls}'><td>{c.seq}</td><td>{html.escape(c.agent)}</td>"
            f"<td>{html.escape(c.trigger)}</td><td>{html.escape(writes)}</td>"
            f"<td class='num'>{c.usage.total}</td></tr>"
        )
    return "\n".join(rows)


def _worm_html(rec) -> str:
    rows = []
    for e in rec.events:
        rows.append(
            f"<tr><td>{e.seq}</td><td>{html.escape(e.agent)}</td>"
            f"<td>{html.escape(e.field)}</td>"
            f"<td class='num'>{html.escape(str(e.old))} → {html.escape(str(e.new))}</td></tr>"
        )
    return "\n".join(rows)


def render_html(orch: dict, bb: dict, scenario: str) -> str:
    o, b = orch["recorder"], bb["recorder"]
    ou, bu = o.total_usage, b.total_usage
    max_calls = max(o.n_calls, b.n_calls, 1)
    o_bar = int(100 * o.n_calls / max_calls)
    b_bar = int(100 * b.n_calls / max_calls)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Orchestrator vs Blackboard — run report</title>
<style>
  :root {{ --bg:#0f1117; --card:#181b24; --line:#2a2f3c; --fg:#e6e8ee;
           --muted:#9aa3b2; --orch:#8a94a6; --bb:#7ec24a; --chg:#7ec24a; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:32px; background:var(--bg); color:var(--fg);
          font:14px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }}
  h1 {{ font-size:22px; margin:0 0 4px; }}
  .sub {{ color:var(--muted); margin:0 0 24px; max-width:70ch; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
           padding:18px; }}
  .card h2 {{ margin:0 0 12px; font-size:15px; }}
  .orch h2 {{ color:var(--orch); }} .bb h2 {{ color:var(--bb); }}
  table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
  th,td {{ text-align:left; padding:5px 8px; border-bottom:1px solid var(--line); }}
  th {{ color:var(--muted); font-weight:600; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; color:var(--muted); }}
  tr.noop td {{ color:var(--muted); opacity:.65; }}
  tr.chg td:first-child {{ border-left:2px solid var(--chg); }}
  .metrics {{ margin-top:24px; }}
  .bar {{ height:22px; border-radius:6px; margin:4px 0 2px; }}
  .bar.o {{ background:var(--orch); width:{o_bar}%; }}
  .bar.b {{ background:var(--bb); width:{b_bar}%; }}
  .kpi {{ display:flex; gap:28px; flex-wrap:wrap; margin-top:14px; }}
  .kpi div b {{ font-size:20px; }} .kpi div span {{ color:var(--muted); }}
  code {{ color:var(--bb); }}
</style></head>
<body>
  <h1>Orchestrator vs Blackboard</h1>
  <p class="sub">Same agents, same task — two control models. Scenario:
     {html.escape(scenario)}</p>

  <div class="metrics card">
    <h2>Cost to converge</h2>
    <div>Orchestrator — {o.n_calls} calls, {ou.total} tokens</div>
    <div class="bar o"></div>
    <div>Blackboard — {b.n_calls} calls, {bu.total} tokens</div>
    <div class="bar b"></div>
    <div class="kpi">
      <div><b>{o.n_calls / max(b.n_calls, 1):.2f}×</b><br><span>fewer agent calls</span></div>
      <div><b>{ou.total / max(bu.total, 1):.2f}×</b><br><span>fewer tokens</span></div>
      <div><b>{o.n_wasted}</b><br><span>orchestrator no-op calls</span></div>
      <div><b>{"yes" if orch["state"] == bb["state"] else "no"}</b><br><span>same final plan</span></div>
    </div>
  </div>

  <div class="grid" style="margin-top:20px">
    <div class="card orch">
      <h2>Orchestrator — fixed-order sweeps</h2>
      <table><thead><tr><th>#</th><th>agent</th><th>trigger</th><th>write</th><th class="num">tok</th></tr></thead>
      <tbody>{_calls_html(o)}</tbody></table>
    </div>
    <div class="card bb">
      <h2>Blackboard — event cascade</h2>
      <table><thead><tr><th>#</th><th>agent</th><th>trigger</th><th>write</th><th class="num">tok</th></tr></thead>
      <tbody>{_calls_html(b)}</tbody></table>
    </div>
  </div>

  <div class="card bb" style="margin-top:20px">
    <h2>Blackboard WORM log — every write, append-only (audit trail)</h2>
    <table><thead><tr><th>seq</th><th>agent</th><th>field</th><th>old → new</th></tr></thead>
    <tbody>{_worm_html(b)}</tbody></table>
  </div>
</body></html>"""
