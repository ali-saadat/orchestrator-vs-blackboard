"""Self-contained animated HTML report.

Embeds each topology's WORM event stream and animates them side by side: a play/
scrub control walks a global cursor; each panel reveals its events up to the
cursor and live-updates meters (calls, tokens, $ cost, writes) computed from the
revealed events. This is the offline "money shot" — the v0.2 dashboard renders the
same contract live over SSE.
"""
from __future__ import annotations

import json

from ..contracts import EngineResult

_CSS = """
:root{--bg:#0f1117;--card:#161922;--line:#272c39;--fg:#e6e8ee;--mut:#9aa3b2;
--orch:#8a94a6;--bb:#7ec24a;--hy:#e0a72b;--chg:#7ec24a;--now:#3b82f6}
*{box-sizing:border-box}body{margin:0;padding:28px;background:var(--bg);color:var(--fg);
font:13.5px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
h1{font-size:21px;margin:0 0 2px}.sub{color:var(--mut);margin:0 0 18px;max-width:80ch}
.controls{display:flex;gap:12px;align-items:center;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:12px 16px;margin-bottom:18px;position:sticky;top:12px;z-index:5}
button{background:#222736;color:var(--fg);border:1px solid var(--line);border-radius:7px;
padding:6px 12px;cursor:pointer;font-size:13px}button:hover{border-color:#3a4257}
input[type=range]{flex:1;accent-color:var(--now)}.tag{font-variant-numeric:tabular-nums;color:var(--mut)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;min-width:0}
.card h2{margin:0 0 10px;font-size:14px}.orch h2{color:var(--orch)}.bb h2{color:var(--bb)}.hy h2{color:var(--hy)}
.meters{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:10px}
.meter b{font-size:19px;font-variant-numeric:tabular-nums}.meter span{color:var(--mut);font-size:11px;display:block}
.log{max-height:52vh;overflow:auto;font-size:12px;border-top:1px solid var(--line);padding-top:8px}
.ev{padding:3px 6px;border-radius:5px;margin:1px 0;color:var(--mut);border-left:2px solid transparent}
.ev.call{color:var(--fg)}.ev.write{color:var(--chg)}.ev.gate{color:#c9a227}.ev.now{background:#1c2436;border-left-color:var(--now)}
.ev .a{font-weight:600}.done{color:var(--bb);font-weight:600;margin-top:8px}
"""

_JS = """
const DATA = __DATA__;
const engines = Object.keys(DATA);
const maxLen = Math.max(...engines.map(e=>DATA[e].length));
let cursor = maxLen, timer=null;
const slider=document.getElementById('scrub'); slider.max=maxLen; slider.value=maxLen;
const label=document.getElementById('pos');
function meters(evs){let calls=0,wasted=0,tin=0,tout=0,cost=0,writes=0;
 for(const e of evs){ if(e.kind==='gen_ai.client.call.finished'){calls++; const a=e.attrs;
   tin+=a['gen_ai.usage.input_tokens']||0; tout+=a['gen_ai.usage.output_tokens']||0;
   cost+=a['cost_usd']||0; if(!a['changed'])wasted++;} if(e.kind==='state_write')writes++; }
 return {calls,wasted,tok:tin+tout,cost,writes};}
function evText(e){const a=e.attrs||{};
 if(e.kind==='agent_activated')return `▸ ${e.agent} <span class=tag>[${a.trigger||''}]</span>`;
 if(e.kind==='gen_ai.client.call.finished')return `  ${e.agent} → ${a.changed?'wrote':'no-op'} <span class=tag>${(a['gen_ai.usage.input_tokens']||0)+(a['gen_ai.usage.output_tokens']||0)} tok · $${(a.cost_usd||0).toFixed(5)}</span>`;
 if(e.kind==='state_write')return `    ✎ ${e.agent}: ${a.field} ${a.old} → ${a.new}`;
 if(e.kind==='agent_retriggered')return `    ↻ re-trigger ${e.agent} <span class=tag>(${a.because})</span>`;
 if(e.kind==='gate_checked')return `  ⏛ gate: ${a.passed?'PASS':'…'}`;
 if(e.kind==='run_started')return `● run started`;
 if(e.kind==='run_finished')return `<span class=done>● consistent=${a.consistent}</span>`;
 return e.kind;}
function cls(e){if(e.kind==='gen_ai.client.call.finished')return 'call';
 if(e.kind==='state_write'||e.kind==='agent_retriggered')return 'write';
 if(e.kind==='gate_checked')return 'gate';return '';}
function render(){label.textContent=cursor+' / '+maxLen;
 for(const e of engines){const evs=DATA[e].slice(0,cursor);const m=meters(evs);
  document.getElementById('m-'+e).innerHTML=
   `<div class=meter><b>${m.calls}</b><span>calls</span></div>`+
   `<div class=meter><b>${m.wasted}</b><span>wasted</span></div>`+
   `<div class=meter><b>${m.writes}</b><span>writes</span></div>`+
   `<div class=meter><b>${m.tok}</b><span>tokens</span></div>`+
   `<div class=meter><b>$${m.cost.toFixed(5)}</b><span>cost</span></div>`;
  const log=document.getElementById('log-'+e);
  log.innerHTML=evs.map((ev,i)=>`<div class="ev ${cls(ev)} ${i===cursor-1?'now':''}">${evText(ev)}</div>`).join('');
  log.scrollTop=log.scrollHeight;}}
function play(){if(timer){clearInterval(timer);timer=null;document.getElementById('play').textContent='▶ play';return;}
 if(cursor>=maxLen)cursor=0;document.getElementById('play').textContent='⏸ pause';
 timer=setInterval(()=>{cursor++;slider.value=cursor;if(cursor>=maxLen){clearInterval(timer);timer=null;
  document.getElementById('play').textContent='▶ play';}render();},450);}
document.getElementById('play').onclick=play;
document.getElementById('step').onclick=()=>{if(cursor<maxLen){cursor++;slider.value=cursor;render();}};
document.getElementById('reset').onclick=()=>{cursor=0;slider.value=0;render();};
slider.oninput=()=>{cursor=+slider.value;render();};
render();
"""


def render_html(results: dict[str, EngineResult], scenario: str) -> str:
    data = {name: r.recorder.events_json() for name, r in results.items()}
    panels = []
    css_class = {"orchestrator": "orch", "blackboard": "bb", "hybrid": "hy"}
    for name in results:
        panels.append(
            f'<div class="card {css_class.get(name,"")}"><h2>{name.upper()}</h2>'
            f'<div class="meters" id="m-{name}"></div>'
            f'<div class="log" id="log-{name}"></div></div>'
        )
    js = _JS.replace("__DATA__", json.dumps(data))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ovb — orchestrator vs blackboard vs hybrid</title><style>{_CSS}</style></head>
<body>
<h1>Three harness topologies, one task</h1>
<p class="sub">Same agents, same gate — only the control loop differs. Press play to
watch each harness converge; meters are computed live from the WORM event stream.
Scenario: {scenario}</p>
<div class="controls">
  <button id="play">▶ play</button><button id="step">⏭ step</button>
  <button id="reset">↺ reset</button>
  <input type="range" id="scrub" min="0" value="0"><span class="tag" id="pos"></span>
</div>
<div class="grid">{''.join(panels)}</div>
<script>{js}</script>
</body></html>"""
