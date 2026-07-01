"""Live side-by-side dashboard — standard library only (no uvicorn/React/build step).

`ovb serve` starts a threaded HTTP server. The browser opens an SSE connection to
`/run?...`; the server runs all selected harnesses CONCURRENTLY over the same
"prompt" (scenario params) and streams every event as it happens, tagged by
engine. The page renders, in real time and per engine: the shared-memory board
(flashing on each write), an agent-talk feed (what each agent "says"), an activity
log (activations, writes, re-triggers, gate), and live meters. Compare all three
at once, or focus one independently.

Modes: mock (deterministic, offline), real (live streaming Claude — needs
ANTHROPIC_API_KEY from a local .env), cassette (replay recorded real calls
offline). Same WORM event contract as the CLI and static report.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..config import RunConfig
from ..dotenv import load_dotenv
from ..domain.task import ScenarioParams
from ..eval.runner import run_engine

_ALL = ["orchestrator", "blackboard", "hybrid"]
_MODELS = ["claude-sonnet-5", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"]
# anchor to the repo root so `ovb serve` replays the committed cassette from any CWD
DEMO_CASSETTE = str(Path(__file__).resolve().parents[3] / "cassettes" / "demo.json")


class _Disconnected(Exception):
    pass


async def _pump(params: ScenarioParams, engine_names, delay: float, write_ev,
                *, mode: str = "mock", model: str = "claude-sonnet-5",
                cassette: str | None = None):
    """Run the selected engines concurrently, streaming their events interleaved."""
    q: asyncio.Queue = asyncio.Queue()
    real = mode == "real"
    eff_delay = 0.0 if real else delay        # real runs are paced by model latency

    def make_sink(name):
        def sink(ev):
            d = ev.model_dump()
            d["engine"] = name
            q.put_nowait(d)
        return sink

    write_ev({"engine": "_meta", "kind": "start",
              "attrs": {"engines": engine_names, "mode": mode, "model": model,
                        "params": {"features": params.requested_features,
                                   "budget": params.budget_cap_k}}})

    async def run_one(name):
        cfg = RunConfig(step_delay=eff_delay, real=real, model=model,
                        cassette=(cassette if mode == "cassette" else None))
        try:
            await run_engine(name, cfg, params, event_sink=make_sink(name))
        except Exception as exc:  # surface per-engine failures to the UI
            q.put_nowait({"engine": name, "kind": "error",
                          "attrs": {"msg": f"{type(exc).__name__}: {exc}"}})
        finally:
            q.put_nowait({"engine": name, "kind": "engine_done", "attrs": {}})

    runners = asyncio.ensure_future(
        asyncio.gather(*[run_one(n) for n in engine_names], return_exceptions=True))
    done = 0
    try:
        while done < len(engine_names):
            ev = await q.get()
            write_ev(ev)
            if ev.get("kind") == "engine_done":
                done += 1
        write_ev({"engine": "_meta", "kind": "all_done", "attrs": {}})
    finally:
        if not runners.done():
            runners.cancel()
        await asyncio.gather(runners, return_exceptions=True)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/run":
            self._run(urllib.parse.parse_qs(parsed.query))
        elif parsed.path == "/health":
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
        else:
            self.send_response(404); self.end_headers()

    def _run(self, qs):
        # defensive parsing: a hand-edited/auto-run URL must never crash the handler
        def one(k, d):
            return (qs.get(k, [d]) or [d])[0]

        def _int(k, d):
            try:
                return int(one(k, str(d)))
            except (TypeError, ValueError):
                return d

        def _float(k, d):
            try:
                return float(one(k, str(d)))
            except (TypeError, ValueError):
                return d

        features = max(0, min(50, _int("features", 8)))
        budget = max(1, min(100000, _int("budget", 90)))
        engines = one("engines", ",".join(_ALL)).split(",")
        engines = [e for e in engines if e in _ALL] or list(_ALL)
        delay = max(0.0, min(2.0, _float("delay", 0.35)))
        mode = one("mode", "mock")
        mode = mode if mode in ("mock", "real", "cassette") else "mock"
        model = one("model", "claude-sonnet-5")
        model = model if model in _MODELS else "claude-sonnet-5"
        params = ScenarioParams(requested_features=features, budget_cap_k=budget)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        alive = {"ok": True}

        def write_ev(obj):
            if not alive["ok"]:
                raise _Disconnected()
            try:
                self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ValueError):
                alive["ok"] = False
                raise _Disconnected()

        # one clear message instead of three cryptic per-engine cassette misses
        if mode == "cassette" and not os.path.exists(DEMO_CASSETTE):
            try:
                write_ev({"engine": "_meta", "kind": "error", "attrs": {
                    "msg": f"cassette not found at {DEMO_CASSETTE} — record it with: "
                           f"ovb bench --real --cassette {DEMO_CASSETTE}"}})
            except Exception:
                pass
            return

        try:
            asyncio.run(_pump(params, engines, delay, write_ev, mode=mode,
                              model=model, cassette=DEMO_CASSETTE))
        except _Disconnected:
            pass
        except Exception as exc:
            try:
                write_ev({"engine": "_meta", "kind": "error", "attrs": {"msg": str(exc)}})
            except Exception:
                pass

    def log_message(self, *args):
        pass


def serve(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True):
    load_dotenv()  # so Real mode finds ANTHROPIC_API_KEY
    httpd = ThreadingHTTPServer((host, port), _Handler)
    url = f"http://{host}:{port}/"
    print(f"ovb live dashboard → {url}   (Ctrl-C to stop)")
    if open_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping…")
    finally:
        httpd.server_close()


# --------------------------------------------------------------------------- UI
INDEX_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ovb — live: orchestrator vs blackboard vs hybrid</title>
<style>
:root{--bg:#0f1117;--card:#161922;--line:#272c39;--fg:#e6e8ee;--mut:#9aa3b2;
--orchestrator:#8a94a6;--blackboard:#63c750;--hybrid:#e0a72b;--now:#3b82f6;--bad:#e06c75;
/* semantic colors, deliberately distinct from the 3 engine hues above */
--ok:#3ecf8e;--write:#4fd1c5;--retrig:#c792ea}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:13.5px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{padding:16px 22px 0}h1{font-size:19px;margin:0}.sub{color:var(--mut);margin:2px 0 0;font-size:12.5px}
.bar{display:flex;gap:13px;align-items:center;flex-wrap:wrap;background:var(--card);
border:1px solid var(--line);border-radius:11px;padding:11px 16px;margin:14px 22px;position:sticky;top:8px;z-index:9}
.bar label{color:var(--mut);font-size:12px;display:flex;gap:6px;align-items:center}
input[type=number]{width:60px}input,select{background:#0e1220;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:5px 7px}
input[type=range]{accent-color:var(--now);width:110px;padding:0}
.chk{display:flex;gap:5px;align-items:center}
button{background:#222736;color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:7px 14px;cursor:pointer;font-size:13px}
button:hover{border-color:#3a4257}button.run{background:var(--now);border-color:var(--now);color:#fff;font-weight:600}
.tabs{margin-left:auto;display:flex;gap:6px}.tabs button.on{background:#2a3350;border-color:var(--now)}
#note{color:#e0a72b;font-size:11.5px;margin:0 22px 6px;min-height:14px}
.grid{display:grid;gap:14px;padding:0 22px 26px}
.grid.n1,.grid.focus{grid-template-columns:1fr}.grid.n2{grid-template-columns:1fr 1fr}.grid.n3{grid-template-columns:1fr 1fr 1fr}
@media(max-width:1050px){.grid.n2,.grid.n3{grid-template-columns:1fr}.bar{position:static}}
@media(max-width:520px){.board{grid-template-columns:repeat(2,1fr)}}
.panel{background:var(--card);border:1px solid var(--line);border-top:3px solid var(--e,#666);border-radius:12px;padding:14px;min-width:0}
.phead{display:flex;align-items:center;gap:9px;margin-bottom:10px}.phead h3{margin:0;font-size:15px;text-transform:capitalize;color:var(--e)}
.cm{color:var(--mut);font-size:11px}.steps{margin-left:auto;color:var(--mut);font-size:11px;font-variant-numeric:tabular-nums}
.dot{width:9px;height:9px;border-radius:50%;background:#555;flex:none}.dot.run{background:var(--now);animation:pulse 1s infinite}.dot.done{background:var(--ok)}.dot.err{background:var(--bad)}
@keyframes pulse{50%{opacity:.35}}
.board{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-bottom:10px}
.cell{background:#0e1220;border:1px solid var(--line);border-radius:8px;padding:6px 8px;text-align:center}
.cell span{display:block;color:var(--mut);font-size:10px;overflow-wrap:anywhere}.cell b{font-size:15px;font-variant-numeric:tabular-nums}
.cell.flash{animation:fl .8s}@keyframes fl{0%{background:var(--e);color:#0b0d12;transform:scale(1.07)}100%{}}
.meters{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:10px;border-top:1px solid var(--line);padding-top:9px}
.meter b{font-size:16px;font-variant-numeric:tabular-nums}.meter span{display:block;color:var(--mut);font-size:10px}
.feeds{display:grid;grid-template-columns:1fr 1fr;gap:10px}@media(max-width:700px){.feeds{grid-template-columns:1fr}}
.feed h4{margin:0 0 5px;font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}
.talk,.log{height:230px;overflow:auto;font-size:12px;background:#0e1220;border:1px solid var(--line);border-radius:8px;padding:7px}
.grid.focus .talk,.grid.focus .log{height:46vh}
.msg{margin:3px 0;padding:5px 8px;border-radius:7px;background:#151a28;border-left:3px solid var(--c,#888);white-space:pre-wrap;overflow-wrap:anywhere}
.msg .who{font-weight:600;color:var(--c);margin-right:6px}.msg i{color:var(--mut)}.msg b{color:var(--fg)}
.li{padding:1px 3px;color:var(--mut);white-space:pre-wrap;font-variant-numeric:tabular-nums}
.li.call{color:var(--fg)}.li.write{color:var(--write)}.li.retrig{color:var(--retrig)}.li.gate{color:#c9a227;font-weight:600}.li.err{color:var(--bad);font-weight:600}
.hint{color:var(--mut);text-align:center;padding:40px}
</style></head>
<body>
<header><h1>Three harness topologies, live — same prompt, side by side</h1>
<p class="sub">Same agents, same gate. Only the control loop differs. Watch each harness converge in real time:
the shared board, what each agent says, and every re-trigger.</p></header>
<div class="bar">
  <label>features <input type="number" id="features" value="8" min="0" max="50"></label>
  <label>budget $k <input type="number" id="budget" value="90" min="1" max="100000"></label>
  <label>mode <select id="mode"><option value="mock">Mock</option><option value="real">Real API</option><option value="cassette">Cassette</option></select></label>
  <label>model <select id="model"><option>claude-sonnet-5</option><option>claude-sonnet-4-6</option><option>claude-haiku-4-5-20251001</option></select></label>
  <span class="chk"><input type="checkbox" id="c-orchestrator" checked><label for="c-orchestrator" style="color:var(--orchestrator)">orchestrator</label></span>
  <span class="chk"><input type="checkbox" id="c-blackboard" checked><label for="c-blackboard" style="color:var(--blackboard)">blackboard</label></span>
  <span class="chk"><input type="checkbox" id="c-hybrid" checked><label for="c-hybrid" style="color:var(--hybrid)">hybrid</label></span>
  <label>speed <input type="range" id="delay" min="0" max="900" step="50" value="350"></label>
  <button class="run" id="go">▶ Run</button>
  <div class="tabs" id="tabs">
    <button data-v="compare" class="on">Compare</button>
    <button data-v="orchestrator">Orchestrator</button>
    <button data-v="blackboard">Blackboard</button>
    <button data-v="hybrid">Hybrid</button>
  </div>
</div>
<div id="note"></div>
<div class="grid n3" id="grid"><div class="hint">Set the prompt and press <b>Run</b>.</div></div>
<script>
const ALL=['orchestrator','blackboard','hybrid'];
const COLORS={orchestrator:'#8a94a6',blackboard:'#63c750',hybrid:'#e0a72b'};
const CM={orchestrator:'hub · fixed order',blackboard:'shared state · reactive',hybrid:'bounded blackboard + linear tail'};
const AGENTC={Scope:'#6ea8fe',Budget:'#4fd1c5',Timeline:'#d3a6ff',Risk:'#ff8f8f'};  // distinct from engine hues
const FIELDS=['scope','max_scope','budget_k','timeline_weeks','risk'];
let view='compare', es=null, ran=[], S={};
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
// minimal, safe markdown for real-model narration: escape first, then strip
// heading/bullet markers and render **bold** / *italic*.
const md=s=>esc(s).replace(/^\s*#{1,6}\s*/gm,'').replace(/^\s*[-*]\s+/gm,'• ')
  .replace(/\*\*([^*]+?)\*\*/g,'<b>$1</b>').replace(/(?<!\*)\*(?!\*)([^*\n]+?)\*(?!\*)/g,'<i>$1</i>')
  .replace(/`([^`]+?)`/g,'<b>$1</b>');

function selected(){return ALL.filter(e=>$('c-'+e).checked);}
function blank(){return {board:{},calls:0,wasted:0,tok:0,cost:0,steps:0,status:'idle',gate:false,talk:[],log:[],flash:{}};}
function meter(l,v){return `<div class="meter"><b>${v}</b><span>${l}</span></div>`;}

function panelHTML(e){const s=S[e]; if(!s)return `<div class="panel" style="--e:${COLORS[e]}"><div class="hint">${e}: not in this run</div></div>`;
 const board=FIELDS.map(f=>{const v=s.board[f];const fl=s.flash[f]?'flash':'';
   return `<div class="cell ${fl}" style="--e:${COLORS[e]}"><span>${f}</span><b>${v===undefined||v===null?'—':esc(v)}</b></div>`;}).join('');
 const talk=s.talk.map(t=>t.err?`<div class="msg" style="--c:var(--bad)"><span class="who" style="color:var(--bad)">error</span>${esc(t.text)}</div>`
   :`<div class="msg" style="--c:${AGENTC[t.agent]||'#888'}"><span class="who">${esc(t.agent)}</span>${md(t.text)}${t.changed?'':' <i>(no change)</i>'}</div>`).join('');
 const log=s.log.map(l=>`<div class="li ${l.cls||''}">${esc(l.t)}</div>`).join('');
 const dot=s.err?'err':s.status==='running'?'run':s.status==='done'?'done':'';
 return `<div class="panel" style="--e:${COLORS[e]}">
   <div class="phead"><span class="dot ${dot}"></span><h3>${e}</h3><span class="cm">${CM[e]}</span><span class="steps">${s.steps} steps</span></div>
   <div class="board">${board}</div>
   <div class="meters">${meter('calls',s.calls)}${meter('wasted',s.wasted)}${meter('tokens',s.tok)}${meter('cost','$'+s.cost.toFixed(5))}${meter('gate',s.gate?'PASS':'…')}</div>
   <div class="feeds"><div class="feed"><h4>agent talk</h4><div class="talk" id="talk-${e}">${talk}</div></div>
   <div class="feed"><h4>activity · shared memory</h4><div class="log" id="log-${e}">${log}</div></div></div></div>`;}

function render(){const grid=$('grid');
 let shown = view==='compare' ? (ran.length?ran:selected()) : [view];
 grid.className='grid '+(view==='compare'?('n'+Math.max(1,shown.length)):'focus');
 grid.innerHTML=shown.map(panelHTML).join('');
 shown.forEach(e=>{const t=$('talk-'+e);if(t)t.scrollTop=t.scrollHeight;const l=$('log-'+e);if(l)l.scrollTop=l.scrollHeight;});
 requestAnimationFrame(()=>{Object.values(S).forEach(s=>s.flash={});});}

function handle(ev){const e=ev.engine,a=ev.attrs||{};
 if(e==='_meta'){if(ev.kind==='all_done'&&es){es.close();es=null;} if(ev.kind==='error'){$('note').textContent='error: '+a.msg;} return;}
 const s=S[e]; if(!s)return;
 switch(ev.kind){
  case 'run_started': s.status='running'; break;
  case 'agent_activated': s.steps++; s.log.push({t:`▸ ${ev.agent}  [${a.trigger||''}]`}); break;
  case 'gen_ai.client.call.finished':{const tin=a['gen_ai.usage.input_tokens']||0,tout=a['gen_ai.usage.output_tokens']||0;
    s.calls++; s.tok+=tin+tout; s.cost+=a.cost_usd||0; if(!a.changed)s.wasted++;
    s.talk.push({agent:ev.agent,text:a.message||'',changed:a.changed});
    s.log.push({t:`  ${ev.agent} → ${a.changed?'wrote':'no-op'}  (${tin+tout} tok · $${(a.cost_usd||0).toFixed(5)})`,cls:'call'}); break;}
  case 'state_write': s.board[a.field]=a.new; s.flash[a.field]=true;
    s.log.push({t:`    ✎ ${a.field}: ${a.old} → ${a.new}`,cls:'write'}); break;
  case 'agent_retriggered': s.log.push({t:`    ↻ re-trigger ${ev.agent}  (${a.because})`,cls:'retrig'}); break;
  case 'gate_checked': s.gate=a.passed; s.log.push({t:`  ⏛ gate: ${a.passed?'PASS ✓':'…'}`,cls:'gate'}); break;
  case 'run_finished': s.status='done'; if(a.state)s.board=a.state; if(a.consistent!==undefined)s.gate=a.consistent; break;
  case 'engine_done': if(!s.err)s.status='done'; break;
  case 'error': s.err=true; s.status='error'; s.talk.push({err:true,text:a.msg}); s.log.push({t:`  ✗ ${a.msg}`,cls:'err'}); break;
 }
 render();}

function run(){ran=selected(); if(!ran.length){alert('select at least one engine');return;}
 S={}; ran.forEach(e=>S[e]=blank());
 if(!['compare',...ran].includes(view))view='compare';
 syncTabs(); render();
 const mode=$('mode').value;
 $('note').textContent = mode==='real' ? 'Real mode: live Claude calls — uses your API key and costs tokens. Paced by model latency.'
   : mode==='cassette' ? 'Cassette mode: replaying recorded real calls offline (record with: ovb bench --real --cassette '+CASS+').' : '';
 if(es)es.close();
 const q=`features=${+$('features').value||0}&budget=${+$('budget').value||1}&engines=${ran.join(',')}`
   +`&delay=${(+$('delay').value)/1000}&mode=${mode}&model=${encodeURIComponent($('model').value)}`;
 es=new EventSource('/run?'+q);
 es.onmessage=m=>handle(JSON.parse(m.data));
 es.onerror=()=>{if(es){es.close();es=null;}
  let dirty=false;
  Object.values(S).forEach(s=>{if(s.status==='running'){s.status='error';s.err=true;s.log.push({t:'  ✗ connection lost',cls:'err'});dirty=true;}});
  if(dirty){$('note').textContent='connection to server lost — run interrupted';render();}};}

const CASS='cassettes/demo.json';
function syncTabs(){document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('on',b.dataset.v===view));}
document.querySelectorAll('#tabs button').forEach(b=>b.onclick=()=>{view=b.dataset.v;syncTabs();render();});
$('go').onclick=run;
// optional auto-run from URL params (handy for shareable links & screenshots):
// /?auto=1&mode=cassette&features=8&budget=90&delay=0&view=compare
(function(){const q=new URLSearchParams(location.search);
 ['features','budget','mode','model','delay'].forEach(k=>{if(q.has(k))$(k).value=q.get(k);});
 if(q.get('view')){view=q.get('view');syncTabs();}
 if(q.get('auto'))run();})();
</script>
</body></html>
"""
