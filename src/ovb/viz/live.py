"""Live side-by-side dashboard — standard library only (no uvicorn/React/build step).

`ovb serve` starts a threaded HTTP server. The browser opens an SSE connection to
`/run?...`; the server runs all selected harnesses CONCURRENTLY over the same
"prompt" (scenario params) and STREAMS every event as it happens (streaming
Messages API under the hood — never the Batch API). Per engine, in real time, the
page shows: an animated flow diagram of the topology, the state board (shared only
for the blackboard/hybrid — the orchestrator has none), an agent-talk feed, an
activity log, and live meters. Compare all at once, focus one, read the glossary.

Modes: mock (deterministic, offline), real (live streaming Claude — needs
ANTHROPIC_API_KEY from a local .env), cassette (replay recorded real calls offline).
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..config import RunConfig
from ..dotenv import load_dotenv
from ..domain.task import ScenarioParams
from ..eval.runner import run_engine

_ALL = ["orchestrator", "blackboard", "hybrid"]
_MODELS = ["claude-haiku-4-5-20251001", "claude-sonnet-5", "claude-opus-4-8",
           "claude-fable-5", "claude-sonnet-4-6"]
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"   # cheapest; model only affects narration cost
# anchor to the repo root so `ovb serve` replays the committed cassette from any CWD
DEMO_CASSETTE = str(Path(__file__).resolve().parents[3] / "cassettes" / "demo.json")

# the immersive story UI lives in real files (lintable, formattable) — see static/
_STATIC_DIR = Path(__file__).resolve().parent / "static"
_STATIC_FILES = {  # allowlist => no path traversal
    "style.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}


class _Disconnected(Exception):
    pass


async def _pump(params: ScenarioParams, engine_names, delay: float, write_ev,
                *, mode: str = "mock", model: str = _DEFAULT_MODEL,
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
                        "params": {"guests": params.wanted_guests,
                                   "budget": params.budget_cap}}})

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
    def _send(self, body: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            # the immersive story journey (simple-English, gamified)
            self._send((_STATIC_DIR / "index.html").read_bytes(),
                       "text/html; charset=utf-8")
        elif parsed.path.startswith("/static/"):
            name = parsed.path[len("/static/"):]
            if name in _STATIC_FILES:
                self._send((_STATIC_DIR / name).read_bytes(), _STATIC_FILES[name])
            else:
                self.send_response(404); self.end_headers()
        elif parsed.path == "/expert":
            # the full expert dashboard (unchanged)
            self._send(INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif parsed.path == "/info":
            info = {"cassette": os.path.exists(DEMO_CASSETTE),
                    "defaults": {"guests": 15, "budget": 600}}
            self._send(json.dumps(info).encode("utf-8"),
                       "application/json; charset=utf-8")
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

        guests = max(1, min(50, _int("guests", 15)))
        budget = max(1, min(100000, _int("budget", 600)))
        engines = one("engines", ",".join(_ALL)).split(",")
        engines = [e for e in engines if e in _ALL] or list(_ALL)
        delay = max(0.0, min(2.0, _float("delay", 0.35)))
        mode = one("mode", "mock")
        mode = mode if mode in ("mock", "real", "cassette") else "mock"
        model = one("model", _DEFAULT_MODEL)
        model = model if model in _MODELS else _DEFAULT_MODEL
        params = ScenarioParams(wanted_guests=guests, budget_cap=budget)

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


def _lan_ips():
    """Non-loopback IPv4 addresses, so testers on the same Wi-Fi/VPN can reach the
    dashboard without any external tunnel — the reliable path on a managed/corporate
    Mac where ngrok is likely blocked by endpoint security (Jamf/Netskope DLP)."""
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))          # no packets sent; just picks the route
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    return sorted(i for i in ips if not i.startswith("127."))


def _find_ngrok():
    p = shutil.which("ngrok")
    if p:
        return p
    for c in ("/opt/homebrew/bin/ngrok", "/usr/local/bin/ngrok",
              os.path.expanduser("~/bin/ngrok"), "/snap/bin/ngrok",
              "/usr/bin/ngrok"):
        if os.path.exists(c):
            return c
    return None


def _start_ngrok(port: int):
    """Open a public ngrok tunnel via the ngrok CLI + its local API. Returns
    (process, public_url) or (proc|None, None). Needs NGROK_AUTHTOKEN (in .env)
    and the `ngrok` binary. No Python dependency."""
    ngrok = _find_ngrok()
    if not ngrok:
        print("  ngrok: binary not found (install from ngrok.com) — skipping tunnel")
        return None, None
    token = os.environ.get("NGROK_AUTHTOKEN")
    if not token:
        print("  ngrok: NGROK_AUTHTOKEN not set (add it to .env) — skipping tunnel")
        return None, None
    # configure the token once (idempotent), then open the tunnel. Never let a
    # broken/misconfigured ngrok take down the dashboard — degrade to local-only.
    try:
        subprocess.run([ngrok, "config", "add-authtoken", token],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        proc = subprocess.Popen(
            [ngrok, "http", str(port), "--log", "stdout"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=dict(os.environ),
        )
    except (OSError, ValueError) as exc:
        print(f"  ngrok: failed to launch ({exc}) — serving locally only")
        return None, None
    for _ in range(40):   # poll the ngrok local API for the assigned URL
        try:
            with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=1) as r:
                for t in json.loads(r.read()).get("tunnels", []):
                    if t.get("public_url", "").startswith("https"):
                        return proc, t["public_url"]
        except Exception:
            pass
        time.sleep(0.5)
    return proc, None


def serve(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True,
          ngrok: bool = False):
    load_dotenv()  # so Real mode finds ANTHROPIC_API_KEY (and NGROK_AUTHTOKEN)
    httpd = ThreadingHTTPServer((host, port), _Handler)
    on_all = host in ("", "0.0.0.0")
    local = f"http://{'127.0.0.1' if on_all else host}:{port}/"
    print(f"ovb live dashboard → {local}   (Ctrl-C to stop)")
    if on_all:  # LAN mode: share on the local network (no external tunnel)
        for ip in _lan_ips():
            print(f"  🖧 LAN (same Wi-Fi/VPN) → http://{ip}:{port}/")

    ng_proc, public = (None, None)
    if ngrok:
        ng_proc, public = _start_ngrok(port)
        if public:
            print(f"  🌐 public URL (ngrok) → {public}")
        else:
            print("  ngrok: no public URL. On a managed/corporate Mac (Jamf/Netskope DLP)")
            print("         it's often blocked — use `ovb serve --lan` for same-network access.")

    if open_browser:
        target = public or local
        threading.Timer(0.7, lambda: webbrowser.open(target)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping…")
    finally:
        httpd.server_close()
        if ng_proc:
            ng_proc.terminate()


# --------------------------------------------------------------------------- UI
INDEX_HTML = r"""<!doctype html>
<html lang="en" data-theme="dark"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ovb — live: orchestrator vs blackboard vs hybrid</title>
<script>try{document.documentElement.dataset.theme=localStorage.getItem('ovb-theme')||'dark'}catch(e){}</script>
<style>
:root{--bg:#0f1117;--card:#161922;--line:#272c39;--fg:#e6e8ee;--mut:#9aa3b2;--feed:#0e1220;--feed2:#151a28;
--orchestrator:#8a94a6;--blackboard:#63c750;--hybrid:#e0a72b;--now:#3b82f6;--bad:#e06c75;
--ok:#3ecf8e;--write:#2dd4bf;--retrig:#c792ea;--gate:#c9a227;--edge:#5a6478}
html[data-theme="light"]{--bg:#f4f6f9;--card:#ffffff;--line:#dfe4ec;--fg:#1b2230;--mut:#5c6675;--feed:#eef1f6;--feed2:#e9edf3;
--orchestrator:#5f6a7d;--blackboard:#2f9e2a;--hybrid:#b9781a;--now:#2563eb;--bad:#d64550;
--ok:#0f9d63;--write:#0d9488;--retrig:#7c3aed;--gate:#8a6d00;--edge:#8b96a8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:13.5px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{padding:16px 22px 0;display:flex;align-items:flex-start;gap:16px}
h1{font-size:19px;margin:0}.sub{color:var(--mut);margin:2px 0 0;font-size:12.5px;max-width:96ch}
#themebtn{margin-left:auto;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 10px;cursor:pointer;font-size:15px;color:var(--fg)}
.bar{display:flex;gap:13px;align-items:center;flex-wrap:wrap;background:var(--card);
border:1px solid var(--line);border-radius:11px;padding:11px 16px;margin:14px 22px;position:sticky;top:8px;z-index:9}
.bar label{color:var(--mut);font-size:12px;display:flex;gap:6px;align-items:center}
input[type=number]{width:60px}input,select{background:var(--feed);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:5px 7px}
input[type=range]{accent-color:var(--now);width:110px;padding:0}
.chk{display:flex;gap:5px;align-items:center}
button{background:#222736;color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:7px 14px;cursor:pointer;font-size:13px}
html[data-theme="light"] button:not(.run):not(.on){background:#eef1f6;color:var(--fg)}
button:hover{border-color:#3a4257}button.run{background:var(--now);border-color:var(--now);color:#fff;font-weight:600}
.tabs{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap}.tabs button.on{background:#2a3350;border-color:var(--now)}
html[data-theme="light"] .tabs button.on{background:#dbe5fb}
#note{color:var(--hybrid);font-size:11.5px;margin:0 22px 6px;min-height:14px}
.grid{display:grid;gap:14px;padding:0 22px 26px}
.grid.n1,.grid.focus{grid-template-columns:1fr}.grid.n2{grid-template-columns:1fr 1fr}.grid.n3{grid-template-columns:1fr 1fr 1fr}
@media(max-width:1050px){.grid.n2,.grid.n3{grid-template-columns:1fr}.bar{position:static}}
@media(max-width:520px){.board{grid-template-columns:repeat(2,1fr)}}
.panel{background:var(--card);border:1px solid var(--line);border-top:3px solid var(--e,#666);border-radius:12px;padding:14px;min-width:0}
.phead{display:flex;align-items:center;gap:9px;margin-bottom:8px}.phead h3{margin:0;font-size:15px;text-transform:capitalize;color:var(--e)}
.cm{color:var(--mut);font-size:11px}.steps{margin-left:auto;color:var(--mut);font-size:11px;font-variant-numeric:tabular-nums}
.dot{width:9px;height:9px;border-radius:50%;background:#555;flex:none}.dot.run{background:var(--now);animation:pulse 1s infinite}.dot.done{background:var(--ok)}.dot.err{background:var(--bad)}
@keyframes pulse{50%{opacity:.35}}
/* flow diagram */
svg.flow{width:100%;height:120px;display:block;background:var(--feed);border:1px solid var(--line);border-radius:8px}
.fx{stroke:var(--edge);stroke-width:1.6;fill:none;opacity:.85}
.fx.on{stroke-width:2.6;opacity:1;stroke-dasharray:5 4;animation:dash .85s linear}
.fx.on.rev{animation:dashrev .85s linear}
.fx.on.msg{stroke:var(--now)}.fx.on.write{stroke:var(--write)}.fx.on.retrig{stroke:var(--retrig)}
@keyframes dash{from{stroke-dashoffset:18}to{stroke-dashoffset:0}}
@keyframes dashrev{from{stroke-dashoffset:0}to{stroke-dashoffset:18}}
.node rect{fill:var(--card);stroke:var(--nc,#888);stroke-width:1.6}
.node.nboard rect{stroke:var(--blackboard);stroke-width:2.4}
.node text{fill:var(--fg);font-size:8.6px;text-anchor:middle;font-weight:600;font-family:ui-sans-serif,system-ui}
.node.nsup rect{stroke-width:2}
html[data-theme="light"] .node rect{stroke-width:2}
html[data-theme="light"] .node.nagent rect{filter:saturate(1.3) brightness(.78)}
.node.pulse rect{animation:npulse .85s}@keyframes npulse{0%{filter:brightness(1.7)}100%{}}
.flowcap{fill:var(--mut);font-size:9px;text-anchor:middle}
marker path{fill:var(--edge)}
.legend{display:flex;gap:12px;margin:6px 0 10px;font-size:10.5px;color:var(--mut)}
.legend i{display:inline-block;width:10px;height:3px;border-radius:2px;margin-right:4px;vertical-align:middle}
.blabel{font-size:10.5px;color:var(--mut);margin:2px 0 5px}
.board{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-bottom:10px}
.cell{background:var(--feed);border:1px solid var(--line);border-radius:8px;padding:6px 8px;text-align:center}
.cell span{display:block;color:var(--mut);font-size:10px;overflow-wrap:anywhere}.cell b{font-size:15px;font-variant-numeric:tabular-nums}
.cell.flash{animation:fl .8s}@keyframes fl{0%{background:var(--e);color:#0b0d12;transform:scale(1.07)}100%{}}
.meters{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:10px;border-top:1px solid var(--line);padding-top:9px}
.meter b{font-size:16px;font-variant-numeric:tabular-nums}.meter span{display:block;color:var(--mut);font-size:10px}
.feeds{display:grid;grid-template-columns:1fr 1fr;gap:10px}@media(max-width:700px){.feeds{grid-template-columns:1fr}}
.feed h4{margin:0 0 5px;font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}
.talk,.log{height:210px;overflow:auto;font-size:12px;background:var(--feed);border:1px solid var(--line);border-radius:8px;padding:7px}
.grid.focus .talk,.grid.focus .log{height:44vh}
.msg{margin:3px 0;padding:5px 8px;border-radius:7px;background:var(--feed2);border-left:3px solid var(--c,#888);white-space:pre-wrap;overflow-wrap:anywhere}
.msg .who{font-weight:600;color:var(--c);margin-right:6px}.msg i{color:var(--mut)}.msg b{color:var(--fg)}
.li{padding:1px 3px;color:var(--mut);white-space:pre-wrap;font-variant-numeric:tabular-nums}
.li.call{color:var(--fg)}.li.write{color:var(--write)}.li.retrig{color:var(--retrig)}.li.gate{color:var(--gate);font-weight:600}.li.err{color:var(--bad);font-weight:600}
.hint{color:var(--mut);text-align:center;padding:40px}
/* how-to guide */
.howto{margin:10px 22px 0;background:var(--card);border:1px solid var(--line);border-radius:11px;padding:2px 16px}
.howto>summary{cursor:pointer;color:var(--fg);font-weight:600;font-size:13px;padding:9px 0;list-style:none}
.howto>summary::-webkit-details-marker{display:none}
.howto-body{padding:2px 0 12px}
.howto-body p{margin:6px 0;color:var(--fg);font-size:12.5px}
.howto-mech{color:var(--mut)!important;border-top:1px solid var(--line);padding-top:9px;margin-top:9px!important}
/* mode info glyph */
.info{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border:1px solid var(--line);border-radius:50%;color:var(--mut);font-size:11px;font-style:italic;cursor:help;user-select:none}
.info:hover,.info:focus{color:var(--now);border-color:var(--now);outline:none}
/* consolidated comparison table */
#cmp{padding:0 22px 30px}
.cmptable{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;overflow-x:auto}
.cmphead{font-size:14px;font-weight:700;color:var(--fg);margin-bottom:2px}
.cmpsub{display:block;font-weight:400;font-size:11.5px;color:var(--mut);margin-top:2px}
.cmptable table{width:100%;border-collapse:collapse;margin-top:10px;font-size:12.5px}
.cmptable th{text-align:left;color:var(--mut);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.03em;padding:6px 10px;border-bottom:1px solid var(--line)}
.cmptable th.num,.cmptable td.num{text-align:right;font-variant-numeric:tabular-nums}
.cmptable td{padding:8px 10px;border-bottom:1px solid var(--line)}
.cmptable tbody tr:last-child td{border-bottom:none}
.cmptable td.eng{font-weight:600;text-transform:capitalize;color:var(--e);white-space:nowrap}
.cmptable td.eng i{display:inline-block;width:9px;height:9px;border-radius:2px;background:var(--e);margin-right:7px;vertical-align:middle}
.cmptable td.plan{color:var(--fg);font-variant-numeric:tabular-nums;white-space:nowrap}
.marg{display:block;font-size:10px;color:var(--ok);font-weight:600;margin-top:1px}
.g-ok{color:var(--ok);font-weight:600}.g-wait{color:var(--mut)}.g-err{color:var(--bad);font-weight:600}
.cmpnote{margin-top:10px;font-size:11.5px;color:var(--mut);border-top:1px solid var(--line);padding-top:9px}
.cmpnote b{color:var(--fg)}
/* problem card + ELI5/Expert toggle + three ways */
.prob{margin:12px 22px 0;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 20px}
.prob-top{display:flex;align-items:center;gap:12px;margin-bottom:8px}
.prob-eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);font-weight:700}
.prob-eyebrow span{text-transform:none;letter-spacing:0;font-weight:400}
.seg{margin-left:auto;display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.seg button{background:transparent;border:none;border-radius:0;padding:5px 13px;font-size:12px;color:var(--mut)}
.seg button.on{background:var(--now);color:#fff;font-weight:600}
.prob-body p{margin:0 0 8px;font-size:13.5px;line-height:1.55;color:var(--fg)}
.prob-head{font-size:15px;font-weight:700;margin-bottom:6px}
.prob-tip{color:var(--mut);font-size:12px}
.prob-body ul{margin:6px 0;padding-left:20px;font-size:13px;line-height:1.5;color:var(--fg)}
.prob-body li{margin:3px 0}
.ways-h{margin:12px 0 8px;font-size:11px;color:var(--mut);font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.ways-h span{text-transform:none;letter-spacing:0;font-weight:400}
.ways{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
@media(max-width:900px){.ways{grid-template-columns:1fr}}
.way{border:1px solid var(--line);border-top:3px solid var(--e);border-radius:9px;padding:10px 12px;background:var(--feed)}
.way-h{font-weight:700;color:var(--e);font-size:13px;text-transform:capitalize;margin-bottom:4px}
.way-h span{color:var(--mut);font-weight:400;font-size:11.5px;text-transform:none;margin-left:4px}
.way-b{font-size:12.5px;color:var(--fg);line-height:1.5}
.target{margin-top:12px;padding:10px 13px;background:var(--feed);border-left:3px solid var(--now);border-radius:7px;font-size:13px;color:var(--fg);line-height:1.55}
/* clearer feed sub-labels + collapsible agent talk */
.feed h4 .fsub{display:block;font-weight:400;text-transform:none;letter-spacing:0;color:var(--mut);font-size:10px;margin-top:1px}
.mtext{white-space:pre-wrap;overflow-wrap:anywhere}
.mtext.clamp{display:block;max-height:4.6em;overflow:hidden;-webkit-mask-image:linear-gradient(#000 66%,transparent);mask-image:linear-gradient(#000 66%,transparent)}
.msg .more{display:block;color:var(--now);font-size:11px;margin-top:3px;cursor:pointer}
.msg.canexpand{cursor:pointer}
/* glossary */
#glossary{padding:0 22px 30px;max-width:980px}
#glossary .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 24px}
#glossary h2{margin:0 0 4px;font-size:16px}#glossary p.g{color:var(--mut);margin:0 0 16px;font-size:12.5px}
#glossary dt{font-weight:700;margin-top:13px}#glossary dt .k{padding:1px 6px;border-radius:5px;font-size:11px;margin-left:6px;color:#0b0d12}
#glossary dd{margin:3px 0 0;color:var(--fg)}#glossary dd .warn{color:var(--hybrid);font-weight:600}
</style></head>
<body>
<header><div><h1>Orchestrator vs Blackboard vs Hybrid — same job, three ways to run it</h1></div>
<a href="/" style="margin-left:auto;align-self:flex-start;color:var(--now);font-size:12.5px;text-decoration:none;white-space:nowrap;padding:6px 0">🎉 Story view</a>
<button id="themebtn" title="toggle theme" style="margin-left:12px">☀️</button></header>
<section class="prob">
  <div class="prob-top">
    <div class="prob-eyebrow">The problem <span>— in plain English</span></div>
    <div class="seg"><button id="segE" class="on" type="button">ELI5</button><button id="segX" type="button">Expert</button></div>
  </div>
  <div id="probE" class="prob-body">
    <p class="prob-head">Four friends, one birthday party — which way wastes the least?</p>
    <p>Four friends are planning one birthday party. Each owns a piece: the <b>guest list</b>, the <b>budget</b>, the <b>food</b>, and the <b>vibe</b>. Their choices fight each other: you want 15 people, but at $50 a head that's $750 — over the $600 budget. Trim the list to 12 and the pizza order and the vibe change too. They keep nudging the plan until it finally fits.</p>
    <p class="prob-tip">In the panels below, the four friends are the agents <b>Guests · Budget · Food · Vibe</b>, and the “whiteboard” is the shared <b>Board</b>.</p>
  </div>
  <div id="probX" class="prob-body" style="display:none">
    <p>Four specialist agents negotiate one party plan under coupled constraints: <b>guests</b> (want 15), <b>budget</b> (hard cap $600 ÷ $50/guest ⇒ 12 max), <b>pizzas</b> (⌈guests ÷ 3⌉), and <b>vibe</b> (from the headcount: &gt;12 wild, &gt;8 lively, else chill). The headcount drives everything, so trimming it to fit the budget also shrinks the pizza order and calms the vibe — agents re-fire until a fixed point: <b>12 guests · $600 · 4 pizzas · lively</b>. A <b>deterministic gate</b> (never the model) checks convergence and declares done.</p>
    <p>All three schedules reach the same fixed point over a streaming API; they differ only in turn efficiency:</p>
    <ul>
    <li><b style="color:var(--orchestrator)">orchestrator</b> — a hub polls all four in fixed order, looping until stable, plus a confirming no-op sweep. That final all-quiet pass is the <b>hub tax</b>: maximum turns and tokens.</li>
    <li><b style="color:var(--blackboard)">blackboard</b> — a shared state store; a write only wakes the dependents of the changed field. Fewer no-op turns.</li>
    <li><b style="color:var(--hybrid)">hybrid</b> — Guests and Budget (tightest coupling) share the blackboard; Food and Vibe each run once in order.</li>
    </ul>
    <p>Metrics: agent calls, no-op turns, tokens, dollar cost. Lower is more efficient.</p>
  </div>
  <div class="ways-h">Three ways to run the meeting <span>— all reach the same plan</span></div>
  <div class="ways">
    <div class="way" style="--e:var(--orchestrator)"><div class="way-h">Orchestrator<span>· “the boss runs it”</span></div><div class="way-b">A boss asks each friend to speak, one at a time, in a fixed order — looping through all four again and again until nobody changes anything, plus one extra round just to double-check. The most back-and-forth.</div></div>
    <div class="way" style="--e:var(--blackboard)"><div class="way-h">Blackboard<span>· “one shared whiteboard”</span></div><div class="way-b">Everyone writes on one shared whiteboard. When a number changes, only the friends who care about that number chime back in. Far less wasted talk.</div></div>
    <div class="way" style="--e:var(--hybrid)"><div class="way-h">Hybrid<span>· “a bit of both”</span></div><div class="way-b">The two friends who clash the most (Guests &amp; Budget) settle it together on the whiteboard first; then the other two each speak just once. A tidy middle ground.</div></div>
  </div>
  <p class="target">🎯 <b>Same party, every time.</b> For your ask (<b id="hf">15</b> guests, $<b id="hb">600</b>) all three reach the one plan that fits: <b id="tgt">12 guests · $600 · 4 pizzas · lively vibe</b>. The only difference is <b>how much talking and money</b> it took — that’s the comparison table below.</p>
</section>
<div class="bar">
  <label>guests <input type="number" id="guests" value="15" min="1" max="50"></label>
  <label>budget $ <input type="number" id="budget" value="600" min="1" max="100000"></label>
  <label>mode
    <select id="mode">
      <option value="mock">Mock — instant, offline, fake</option>
      <option value="cassette">Cassette — replay recorded real calls</option>
      <option value="real">Real API — live Claude, costs $</option>
    </select>
    <span class="info" tabindex="0" aria-label="mode help" title="Mock: deterministic fake outputs, instant, offline, no API key, no cost. Cassette: replays REAL recorded Claude calls offline — real outputs/tokens/cost, no key, no spend. Real API: live streaming Claude — needs ANTHROPIC_API_KEY, actually costs money.">i</span>
  </label>
  <label>model <select id="model">
    <option value="claude-haiku-4-5-20251001">Haiku 4.5 — $1/$5 (cheapest)</option>
    <option value="claude-sonnet-5">Sonnet 5 — $2/$10</option>
    <option value="claude-opus-4-8">Opus 4.8 — $5/$25</option>
  </select></label>
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
    <button data-v="glossary">Glossary</button>
  </div>
</div>
<div id="note"></div>
<div class="grid n3" id="grid"><div class="hint">Set the prompt and press <b>Run</b>.</div></div>
<div id="cmp"></div>
<div id="glossary" style="display:none"></div>
<script>
const ALL=['orchestrator','blackboard','hybrid'];
const COLORS={orchestrator:'#8a94a6',blackboard:'#63c750',hybrid:'#e0a72b'};
const CM={orchestrator:'hub · fixed order · no shared board',blackboard:'shared board · reactive',hybrid:'bounded board + supervisor tail'};
const AGENTC={Guests:'#6ea8fe',Budget:'#4fd1c5',Food:'#d3a6ff',Vibe:'#ff8f8f'};
const FIELDS=['guests','max_guests','cost','pizzas','vibe'];
const BOARD_LABEL={orchestrator:'supervisor state · fixed-order sweeps · no shared board, no re-triggering',blackboard:'shared blackboard · all agents read/write',hybrid:'shared board (Guests↔Budget core) + supervisor tail'};
const FEED_LABEL={orchestrator:'activity · message passing',blackboard:'activity · shared memory',hybrid:'activity · core shared + tail messages'};
const TOPO={
 orchestrator:{nodes:{SUP:[150,22],Guests:[48,108],Budget:[116,108],Food:[184,108],Vibe:[252,108]},
   edges:[['SUP','Guests'],['SUP','Budget'],['SUP','Food'],['SUP','Vibe']],
   cap:'Supervisor calls each agent in fixed order · blue arrow = a message (no shared board)'},
 blackboard:{nodes:{BB:[150,70],Guests:[50,24],Budget:[250,24],Food:[50,116],Vibe:[250,116]},
   edges:[['BB','Guests'],['BB','Budget'],['BB','Food'],['BB','Vibe']],
   cap:'All agents share one Board · teal = write to board · purple = board re-triggers an agent'},
 hybrid:{nodes:{BB:[74,70],Guests:[34,30],Budget:[34,112],SUP:[188,70],Food:[256,42],Vibe:[256,100]},
   edges:[['BB','Guests'],['BB','Budget'],['BB','SUP'],['SUP','Food'],['SUP','Vibe']],
   cap:'Board core (Guests↔Budget: teal/purple), then Supervisor tail (Food, Vibe: blue message)'}
};
let view='compare', es=null, ran=[], S={};
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const md=s=>esc(s).replace(/^\s*#{1,6}\s*/gm,'').replace(/^\s*[-*]\s+/gm,'• ')
  .replace(/\*\*([^*]+?)\*\*/g,'<b>$1</b>').replace(/(?<!\*)\*(?!\*)([^*\n]+?)\*(?!\*)/g,'<i>$1</i>')
  .replace(/`([^`]+?)`/g,'<b>$1</b>');

function selected(){return ALL.filter(e=>$('c-'+e).checked);}
function blank(){return {board:{},calls:0,wasted:0,writes:0,tok:0,cost:0,steps:0,status:'idle',gate:false,talk:[],log:[],flash:{},flow:null};}
function meter(l,v){return `<div class="meter"><b>${v}</b><span>${l}</span></div>`;}
function setFlow(e,source,target,type){if(S[e])S[e].flow={source,target,type};}

function flowSVG(e){const t=TOPO[e],s=S[e],f=s.flow,N=t.nodes;
 const edges=t.edges.map(([a,b])=>{const[x1,y1]=N[a],[x2,y2]=N[b];
   const on=f&&((f.source===a&&f.target===b)||(f.source===b&&f.target===a));
   const rev=on&&f.source===b;  // line is a→b; flow source is b ⇒ reversed
   const mk=on?(rev?'marker-start="url(#arw)"':'marker-end="url(#arw)"'):'';  // head at the true target
   return `<line class="fx ${on?'on '+f.type+(rev?' rev':''):''}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" ${mk}/>`;}).join('');
 const nodes=Object.entries(N).map(([name,[x,y]])=>{const w=name==='SUP'?68:name==='BB'?58:48,h=18;
   const kind=name==='BB'?'nboard':name==='SUP'?'nsup':'nagent';
   const label=name==='BB'?'Board':name==='SUP'?'Supervisor':name;
   const nc=name==='BB'?'var(--blackboard)':name==='SUP'?COLORS[e]:(AGENTC[name]||'#888');
   const pulse=(f&&f.target===name)?'pulse':'';
   return `<g class="node ${kind} ${pulse}"><rect x="${x-w/2}" y="${y-h/2}" width="${w}" height="${h}" rx="4" style="--nc:${nc}"/><text x="${x}" y="${y+3.4}">${label}</text></g>`;}).join('');
 return `<svg class="flow" viewBox="0 0 300 150" preserveAspectRatio="xMidYMid meet">
   <defs><marker id="arw" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto-start-reverse"><path d="M0,0 L6,3 L0,6 Z"/></marker></defs>
   ${edges}${nodes}<text class="flowcap" x="150" y="145">${t.cap}</text></svg>`;}

function panelHTML(e){const s=S[e];if(!s)return `<div class="panel" style="--e:${COLORS[e]}"><div class="hint">${e}: not in this run</div></div>`;
 const board=FIELDS.map(f=>{const v=s.board[f];const fl=s.flash[f]?'flash':'';
   return `<div class="cell ${fl}" style="--e:${COLORS[e]}"><span>${f}</span><b>${v===undefined||v===null?'—':esc(v)}</b></div>`;}).join('');
 const talk=s.talk.map((t,i)=>{if(t.err)return `<div class="msg" style="--c:var(--bad)"><span class="who" style="color:var(--bad)">error</span>${esc(t.text)}</div>`;
   const long=(t.text||'').length>160 && !t.expanded;
   const body=md(t.text)+(t.changed?'':' <i>(no change)</i>');
   const more=long?`<span class="more" onclick="expandMsg('${e}',${i})">show more ▸</span>`:'';
   return `<div class="msg${long?' canexpand':''}" style="--c:${AGENTC[t.agent]||'#888'}"${long?` onclick="expandMsg('${e}',${i})"`:''}><span class="mtext${long?' clamp':''}"><span class="who">${esc(t.agent)}</span>${body}</span>${more}</div>`;}).join('');
 const log=s.log.map(l=>`<div class="li ${l.cls||''}">${esc(l.t)}</div>`).join('');
 const dot=s.err?'err':s.status==='running'?'run':s.status==='done'?'done':'';
 return `<div class="panel" style="--e:${COLORS[e]}">
   <div class="phead"><span class="dot ${dot}"></span><h3>${e}</h3><span class="cm">${CM[e]}</span><span class="steps">${s.steps} steps</span></div>
   ${flowSVG(e)}
   <div class="legend"><span><i style="background:var(--now)"></i>message</span><span><i style="background:var(--write)"></i>write</span><span><i style="background:var(--retrig)"></i>re-trigger</span></div>
   <div class="blabel">${BOARD_LABEL[e]}</div>
   <div class="board">${board}</div>
   <div class="meters">${meter('calls',s.calls)}${meter('wasted',s.wasted)}${meter('tokens',s.tok)}${meter('cost','$'+s.cost.toFixed(5))}${meter('gate',s.gate?'PASS':'…')}</div>
   <div class="feeds"><div class="feed"><h4>What each friend said<span class="fsub">one specialist per turn, in plain words</span></h4><div class="talk" id="talk-${e}">${talk}</div></div>
   <div class="feed"><h4>Play-by-play<span class="fsub" title="🎤 a turn · ✏️ changed a number · ✅ nothing to change · 🔔 must re-check · 🏁 done-check">every turn &amp; change · hover for key ⓘ</span></h4><div class="log" id="log-${e}">${log}</div></div></div></div>`;}

function fmtPlan(b){const g=k=>b[k]===undefined||b[k]===null?'—':b[k];
  return `${g('guests')} guests · $${g('cost')} · ${g('pizzas')} pizzas · ${g('vibe')}`;}
function ratio(base,val){if(!base||!val||val>=base)return '';return '<span class="marg">'+(base/val).toFixed(2)+'× fewer</span>';}
function comparisonHTML(){
  const engines=(ran.length?ran:selected()).filter(e=>S[e]);
  if(!engines.length)return '';
  const allSamePlan=engines.length>1 && engines.every(e=>fmtPlan(S[e].board)===fmtPlan(S[engines[0]].board));
  const cols=['Engine','Calls','Wasted','State writes','Tokens','Cost $','Steps','Final plan','Gate'];
  const head='<tr>'+cols.map((c,i)=>`<th${i>0&&i<7?' class="num"':''}>${c}</th>`).join('')+'</tr>';
  const rows=engines.map(e=>{const s=S[e];const b=S['orchestrator'];
    const callM=(e!=='orchestrator'&&b)?ratio(b.calls,s.calls):'';
    const tokM =(e!=='orchestrator'&&b)?ratio(b.tok,s.tok):'';
    const costM=(e!=='orchestrator'&&b)?ratio(b.cost,s.cost):'';
    const gate=s.err?'<span class="g-err">error</span>':s.gate?'<span class="g-ok">PASS ✓</span>':'<span class="g-wait">…</span>';
    return `<tr style="--e:${COLORS[e]}"><td class="eng"><i></i>${e}</td>`
      +`<td class="num">${s.calls}${callM}</td>`+`<td class="num">${s.wasted}</td>`
      +`<td class="num">${s.writes}</td>`+`<td class="num">${s.tok}${tokM}</td>`
      +`<td class="num">$${s.cost.toFixed(5)}${costM}</td>`+`<td class="num">${s.steps}</td>`
      +`<td class="plan">${fmtPlan(s.board)}</td>`+`<td>${gate}</td></tr>`;}).join('');
  const note=allSamePlan
    ? '<div class="cmpnote">All engines reached the <b>same final plan</b> — the only differences are the cost of coordination (calls, wasted no-ops, tokens, $). Margins are vs the orchestrator baseline.</div>'
    : '<div class="cmpnote">Run to completion to compare; margins appear vs the orchestrator baseline once available.</div>';
  return `<div class="cmptable"><div class="cmphead">Consolidated comparison — same prompt, same target plan
    <span class="cmpsub">lower is better on every count; the Final plan is identical across engines</span></div>
    <table><thead>${head}</thead><tbody>${rows}</tbody></table>${note}</div>`;}
function render(){const grid=$('grid'),gl=$('glossary'),cmp=$('cmp');
 if(view==='glossary'){grid.style.display='none';cmp.style.display='none';gl.style.display='block';gl.innerHTML=glossaryHTML();syncTabs();return;}
 gl.style.display='none';grid.style.display='grid';
 let shown = view==='compare' ? (ran.length?ran:selected()) : [view];
 grid.className='grid '+(view==='compare'?('n'+Math.max(1,shown.length)):'focus');
 grid.innerHTML=shown.map(panelHTML).join('');
 if(view==='compare'){cmp.style.display='block';cmp.innerHTML=comparisonHTML();}else cmp.style.display='none';
 shown.forEach(e=>{const t=$('talk-'+e);if(t)t.scrollTop=t.scrollHeight;const l=$('log-'+e);if(l)l.scrollTop=l.scrollHeight;});
 requestAnimationFrame(()=>{Object.values(S).forEach(s=>{s.flash={};s.flow=null;});});}

function handle(ev){const e=ev.engine,a=ev.attrs||{};
 if(e==='_meta'){if(ev.kind==='all_done'&&es){es.close();es=null;} if(ev.kind==='error'){$('note').textContent='error: '+a.msg;} return;}
 const s=S[e]; if(!s)return; const core=e==='hybrid'&&(ev.agent==='Guests'||ev.agent==='Budget');
 switch(ev.kind){
  case 'run_started': s.status='running'; break;
  case 'agent_activated': s.steps++; s.log.push({t:`🎤 ${ev.agent}'s turn`});
    if(e==='orchestrator')setFlow(e,'SUP',ev.agent,'msg');
    else if(e==='blackboard')setFlow(e,'BB',ev.agent,'msg');
    else setFlow(e,core?'BB':'SUP',ev.agent,'msg'); break;
  case 'gen_ai.client.call.finished':{const tin=a['gen_ai.usage.input_tokens']||0,tout=a['gen_ai.usage.output_tokens']||0;
    s.calls++; s.tok+=tin+tout; s.cost+=a.cost_usd||0; if(!a.changed)s.wasted++;
    s.talk.push({agent:ev.agent,text:a.message||'',changed:a.changed});
    s.log.push({t:a.changed?`✏️ ${ev.agent} changed something · ${tin+tout} tok · $${(a.cost_usd||0).toFixed(5)}`:`✅ ${ev.agent}: nothing to change · ${tin+tout} tok · $${(a.cost_usd||0).toFixed(5)}`,cls:'call'});
    if(a.changed){if(e==='orchestrator')setFlow(e,ev.agent,'SUP','msg');
      else if(e==='blackboard')setFlow(e,ev.agent,'BB','write');
      else setFlow(e,ev.agent,core?'BB':'SUP',core?'write':'msg');} break;}
  case 'state_write': s.board[a.field]=a.new; s.flash[a.field]=true; s.writes++;
    s.log.push({t:`  ✏️ set ${a.field}: ${a.old} → ${a.new}`,cls:'write'}); break;
  case 'agent_retriggered': s.log.push({t:`  🔔 ${ev.agent} has to re-check (${a.because})`,cls:'retrig'});
    if(e==='blackboard'||(e==='hybrid'&&(ev.agent==='Guests'||ev.agent==='Budget')))setFlow(e,'BB',ev.agent,'retrig'); break;
  case 'gate_checked': s.gate=a.passed; s.log.push({t:`  🏁 done-check: ${a.passed?'every rule satisfied ✓':'not yet…'}`,cls:'gate'}); break;
  case 'run_finished': s.status='done'; if(a.state)s.board=a.state; if(a.consistent!==undefined)s.gate=a.consistent; break;
  case 'engine_done': if(!s.err)s.status='done'; break;
  case 'error': s.err=true; s.status='error'; s.talk.push({err:true,text:a.msg}); s.log.push({t:`  ✗ ${a.msg}`,cls:'err'}); break;
 }
 render();}

function run(){ran=selected(); if(!ran.length){alert('select at least one engine');return;}
 S={}; ran.forEach(e=>S[e]=blank());
 if(!['compare','glossary',...ran].includes(view))view='compare';
 syncTabs(); render();
 const mode=$('mode').value;
 recalcTarget();
 $('note').textContent = MODE_HELP[mode] || '';
 if(es)es.close();
 const q=`guests=${+$('guests').value||1}&budget=${+$('budget').value||1}&engines=${ran.join(',')}`
   +`&delay=${(+$('delay').value)/1000}&mode=${mode}&model=${encodeURIComponent($('model').value)}`;
 es=new EventSource('/run?'+q);
 es.onmessage=m=>handle(JSON.parse(m.data));
 es.onerror=()=>{if(es){es.close();es=null;}
  let dirty=false;
  Object.values(S).forEach(s=>{if(s.status==='running'){s.status='error';s.err=true;s.log.push({t:'  ✗ connection lost',cls:'err'});dirty=true;}});
  if(dirty){$('note').textContent='connection to server lost — run interrupted';render();}};}

const CASS='cassettes/demo.json';
const MODE_HELP={
 mock:'Mock: deterministic fake narration — instant, offline, no API key, no cost. The plan, call counts and structure are identical to a real run; only the wording is stubbed.',
 cassette:'Cassette: replaying RECORDED real Claude calls — you see the real outputs, tokens and cost, but it runs offline with no API key and no new spend (recorded at 15 guests, budget $600; record other cases with: ovb bench --real --cassette '+CASS+').',
 real:'Real API: live STREAMING Claude — uses your ANTHROPIC_API_KEY and spends money. Paced by real model latency.'};
const GLOSS=[
 ['Harness','var(--now)','The deterministic program around the model — the control loop that calls the model, applies its result through the ownership reducer, and checks the gate. Orchestrator, blackboard and hybrid are three harnesses; only the scheduling differs.'],
 ['Orchestrator','var(--orchestrator)','Hub-and-spoke. A central <b>supervisor</b> invokes agents in a fixed order over its accumulated state. <span class="warn">No shared board and no re-triggering</span> — an agent never wakes because another wrote a field; coordination is only the supervisor\'s next sweep. Each call is a fresh model call over the supervisor\'s current state. Converges by re-sweeping the whole roster.'],
 ['Blackboard','var(--blackboard)','Shared-state. All agents read and write ONE shared board. A write <b>re-triggers</b> only the agents subscribed to the changed field, so work is proportional to the ripples, not roster × rounds.'],
 ['Hybrid','var(--hybrid)','A bounded blackboard over the tightly-coupled core (Guests↔Budget), then a linear supervisor tail (Food, Vibe). Gets shared-board reactivity where it helps and message-passing where it does not.'],
 ['Shared board (shared memory)','var(--blackboard)','The single board all agents read/write, with reactive <b>re-triggering</b>. <span class="warn">Exists only in the blackboard and the hybrid core.</span> The orchestrator has none — its state is supervisor-held and updated only by fixed-order sweeps (no reactive board).'],
 ['Supervisor','var(--orchestrator)','The central agent that routes work in a fixed order and holds the state in the orchestrator (and drives the hybrid tail).'],
 ['Knowledge source / agent','var(--now)','A specialist that owns fields and reacts to changes. Here: Guests, Budget, Food, Vibe. Identical across all three harnesses — only the harness (scheduling) differs.'],
 ['Control unit','var(--hybrid)','The deterministic scheduler + iteration cap that drives the blackboard event loop (picks who fires next, bounds the run).'],
 ['Gate','var(--gate)','The deterministic "are we done?" check. The LLM <b>never</b> decides termination — code does.'],
 ['Re-trigger','var(--retrig)','On a shared board, a write wakes the agents subscribed to the changed field (purple arrow in the flow).'],
 ['Write','var(--write)','An agent posts a change to the shared board (teal arrow / ✎ in the log).'],
 ['Message passing','var(--now)','The orchestrator routes context to a sub-agent and gets a result back — no shared state (blue arrow).'],
 ['Wasted call','var(--mut)','A no-op agent call that changed nothing — e.g. the orchestrator\'s confirming final sweep. The "hub tax".'],
 ['WORM log','var(--mut)','The append-only (write-once, read-many) event stream — the audit trail every panel is rendered from.'],
 ['Streaming vs Batch','var(--now)','We use the <b>streaming</b> Messages API (real-time SSE, token-by-token). NOT the Batch API (asynchronous, up to 24h, 50% cheaper) — you would not see the flow.'],
 ['Model choice','var(--ok)','Since decisions are rule-based, the model only <b>narrates</b>. It changes tokens/cost, never the plan or call counts — so the cheapest model (Haiku 4.5, $1/$5) fits. Compare with <code>ovb models</code>.'],
 ['Mock mode','var(--ok)','Deterministic fake narration, generated instantly and fully offline. No API key, no network, no cost. The call counts, writes and gate behaviour are REAL (from the harness); only the model\'s prose is stubbed. Best for understanding the topologies.'],
 ['Cassette mode','var(--now)','Replays a recorded REAL run offline. The outputs, token counts and dollar costs are the actual Claude responses captured earlier with <code>ovb bench --real --cassette</code> — so you see real numbers with <b>no API key and no spend</b>. The committed recording is 15 guests, budget $600.'],
 ['Real API mode','var(--hybrid)','Live <b>streaming</b> Claude calls over the real Messages API. <span class="warn">Needs ANTHROPIC_API_KEY (from a local .env) and actually costs tokens/money.</span> Paced by model latency, not the speed slider.'],
];
function glossaryHTML(){return `<div class="card"><h2>Glossary</h2>
 <p class="g">Precise definitions — mind the wording: the orchestrator has <b>no shared board</b> and no re-triggering; only the blackboard (and the hybrid core) share a board that agents read/write.</p>
 <dl>`+GLOSS.map(([t,c,d])=>`<dt style="color:${c}">${t}</dt><dd>${d}</dd>`).join('')+`</dl></div>`;}

function setTheme(t){document.documentElement.dataset.theme=t;try{localStorage.setItem('ovb-theme',t)}catch(e){}$('themebtn').textContent=t==='light'?'🌙':'☀️';}
$('themebtn').onclick=()=>setTheme(document.documentElement.dataset.theme==='light'?'dark':'light');
setTheme((function(){try{return localStorage.getItem('ovb-theme')}catch(e){return null}})()||'dark');
function syncTabs(){document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('on',b.dataset.v===view));}
document.querySelectorAll('#tabs button').forEach(b=>b.onclick=()=>{view=b.dataset.v;syncTabs();render();});
$('go').onclick=run;
$('mode').onchange=()=>{$('note').textContent=MODE_HELP[$('mode').value]||'';};
$('note').textContent=MODE_HELP[$('mode').value]||'';
// ELI5 / Expert toggle
$('segE').onclick=()=>{$('segE').classList.add('on');$('segX').classList.remove('on');$('probE').style.display='';$('probX').style.display='none';};
$('segX').onclick=()=>{$('segX').classList.add('on');$('segE').classList.remove('on');$('probX').style.display='';$('probE').style.display='none';};
// expand a clamped agent message (inline onclick → must be global)
window.expandMsg=function(e,i){if(S[e]&&S[e].talk[i]){S[e].talk[i].expanded=true;render();}};
// live "expected plan" recompute — mirrors domain/task.py exactly
function recalcTarget(){const want=Math.max(1,Math.min(50,+$('guests').value||1));const cap=Math.max(1,+$('budget').value||1);
 const g=Math.min(want,Math.floor(cap/50));const cost=g*50,pizzas=Math.ceil(g/3);
 const vibe=g>12?'wild':g>8?'lively':'chill';
 $('hf').textContent=want;$('hb').textContent=cap;$('tgt').textContent=`${g} guests · $${cost} · ${pizzas} pizzas · ${vibe} vibe`;}
$('guests').addEventListener('input',recalcTarget);$('budget').addEventListener('input',recalcTarget);recalcTarget();
// optional auto-run from URL params (shareable links & screenshots)
(function(){const q=new URLSearchParams(location.search);
 ['guests','budget','mode','model','delay'].forEach(k=>{if(q.has(k))$(k).value=q.get(k);});
 if(q.get('view')){view=q.get('view');syncTabs();}
 if(q.get('auto'))run();})();
</script>
</body></html>
"""
