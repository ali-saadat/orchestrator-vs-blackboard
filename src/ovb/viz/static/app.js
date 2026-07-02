/* ovb story journey — buffered client-side playback over the same SSE event
   contract the expert dashboard uses. Zero dependencies. */
'use strict';

/* ---------- constants ---------- */
const ALL = ['orchestrator', 'blackboard', 'hybrid'];
const NICE = {
  orchestrator: { name: 'The Boss Way', tech: 'Orchestrator', emoji: '👔', cvar: 'var(--orch)' },
  blackboard:   { name: 'The Whiteboard Way', tech: 'Blackboard', emoji: '📋', cvar: 'var(--bb)' },
  hybrid:       { name: 'The Mix Way', tech: 'Hybrid', emoji: '🤝', cvar: 'var(--hy)' },
};
const FRIENDC = { Candidate: '#6ea8fe', Manager: '#4fd1c5', HR: '#d3a6ff', Finance: '#ff8f8f' };
const FRIENDE = { Candidate: '🙋', Manager: '🧑\u200d💼', HR: '📋', Finance: '💰' };
const CHIPS = [['ask', '🙋 Ask $k'], ['offer', '🧑\u200d💼 Offer $k'], ['salary', '🤝 Salary $k'],
               ['bonus', '💰 Bonus $k'], ['remote', '📋 Remote days']];
const TOPO = {   // 300x150 canvas; agent nodes 68px, hub nodes 72px wide — no overlaps
  orchestrator: { nodes: { SUP: [150, 22], Candidate: [40, 112], Manager: [114, 112], HR: [188, 112], Finance: [262, 112] },
    edges: [['SUP', 'Candidate'], ['SUP', 'Manager'], ['SUP', 'HR'], ['SUP', 'Finance']] },
  blackboard: { nodes: { BB: [150, 75], Candidate: [50, 24], Manager: [250, 24], HR: [50, 126], Finance: [250, 126] },
    edges: [['BB', 'Candidate'], ['BB', 'Manager'], ['BB', 'HR'], ['BB', 'Finance']] },
  hybrid: { nodes: { Candidate: [40, 22], Manager: [40, 75], HR: [40, 128], BB: [118, 75], SUP: [230, 40], Finance: [230, 112] },
    edges: [['BB', 'Candidate'], ['BB', 'Manager'], ['BB', 'HR'], ['BB', 'SUP'], ['SUP', 'Finance']] },
};
const DOTC = { msg: '#4f8dfd', write: '#2dd4bf', retrig: '#c792ea' };

/* ---------- tiny helpers ---------- */
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
const md = (s) => esc(s).replace(/^\s*#{1,6}\s*/gm, '').replace(/^\s*[-*]\s+/gm, '• ')
  .replace(/\*\*([^*]+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+?)`/g, '<b>$1</b>');

/* ---------- global state ---------- */
let INFO = { cassette: false, defaults: { ask: 130, band: 110 } };
let MODE = 'mock';
let GUESS = null;
let raceEngines = [];
let S = {};                 // per-engine live state
let Qs = {};                // per-engine buffered event queues (drained round-robin → a real race)
let rr = 0;                 // round-robin cursor
let es = null, timer = null, speed = 900, winTimer = null;
let allDoneSeen = false, raceFinished = false, finishedShown = false;
const PRE = window.PRELOADED || null;
const EXPECT_SCENARIO = 'job-offer/v1';   // must match the server's /info stamp
let lastErr = '';

function qTotal() { return raceEngines.reduce((n, e) => n + (Qs[e] ? Qs[e].length : 0), 0); }
function qPush(ev) { if (Qs[ev.engine]) Qs[ev.engine].push(ev); }
function drainOne() {
  for (let i = 0; i < raceEngines.length; i++) {
    const e = raceEngines[(rr + i) % raceEngines.length];
    if (Qs[e] && Qs[e].length) {
      rr = (rr + i + 1) % raceEngines.length;
      handle(Qs[e].shift());
      return true;
    }
  }
  return false;
}

/* ---------- theme ---------- */
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem('ovb-story-theme', t); } catch (e) {}
  $('themebtn').textContent = t === 'light' ? '🌙' : '☀️';
}
$('themebtn').onclick = () => setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light');
setTheme(document.documentElement.dataset.theme || 'dark');

/* ---------- scenes ---------- */
let storyPlayed = false;
function go(n) {
  document.querySelectorAll('.scene').forEach((s, i) => s.classList.toggle('active', i === n));
  document.querySelectorAll('#stepper button').forEach((b) => {
    b.classList.toggle('on', +b.dataset.s === n);
    b.classList.toggle('done', +b.dataset.s < n);
  });
  window.scrollTo({ top: 0 });
  if (n === 0 && !storyPlayed) playStory();

/* shareable auto-start links (also used for headless screenshots):
   /?auto=race&speed=300&ask=140&band=115  — starts the full race at that pace */
(function () {
  const q = new URLSearchParams(location.search);
  if (q.get('ask') && $('inAsk')) $('inAsk').value = q.get('ask');
  if (q.get('band') && $('inBand')) $('inBand').value = q.get('band');
  if (q.get('auto') === 'race') {
    const sp = q.get('speed');
    if (sp !== null) {
      const btn = [...document.querySelectorAll('.speeds button')].find((b) => +b.dataset.sp === +sp);
      setSpeed(+sp || 0, btn);
    }
    startRace(ALL);
  }
})();
}
document.querySelectorAll('#stepper button').forEach((b) => {
  b.onclick = () => {
    const n = +b.dataset.s;
    if (n === 2 && !raceEngines.length) { startRace(ALL); return; }
    if (n === 3 && !raceFinished) return;
    go(n);
  };
});

/* scene 1: staggered story + budget bar + the dependency chain */
function flipTo(id, val) {
  const el = $(id); if (!el) return;
  el.textContent = val;
  el.classList.remove('flip'); void el.offsetWidth; el.classList.add('flip');
}
function zap(id) {
  const el = $(id); if (!el) return;
  el.classList.remove('zap'); void el.offsetWidth; el.classList.add('zap');
}
function playChain() {
  $('chain').classList.add('show');
  const t = (ms, fn) => setTimeout(fn, ms);
  t(300,  () => { $('ca1').classList.add('pulse'); $('ca2').classList.add('pulse'); });
  t(900,  () => { zap('cnAsk');   flipTo('chA', '$126k'); });
  t(1700, () => { zap('cnOffer'); flipTo('chO', '$104k'); });
  t(2500, () => { zap('cnAsk');   flipTo('chA', '$123k'); });
  t(3300, () => { zap('cnOffer'); flipTo('chO', '$107k'); });
  t(4100, () => { zap('cnDeal'); });                                        // …and so on, toward the middle
  t(4900, () => { $('ca1').classList.remove('pulse'); $('ca2').classList.remove('pulse'); });
}
function playStory() {
  storyPlayed = true;
  const lines = document.querySelectorAll('#story p');
  lines.forEach((p, i) => setTimeout(() => p.classList.add('show'), 900 + i * 850));
  setTimeout(() => {
    document.querySelector('.budgetbar').classList.add('show');
    $('bbHave').style.width = '80%';
    const over = $('bbOver');
    over.style.left = '80%'; over.style.width = '20%';
  }, 900 + lines.length * 850);
  setTimeout(playChain, 900 + lines.length * 850 + 1500);
}

/* scene 2: looping mini topologies */
function buildMini(svg, kind) {
  const NS = 'http://www.w3.org/2000/svg';
  const mk = (tag, attrs) => { const el = document.createElementNS(NS, tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]); return el; };
  const node = (x, y, label, color, w) => {
    svg.appendChild(mk('rect', { class: 'mn', x: x - w / 2, y: y - 9, width: w, height: 18, rx: 5, stroke: color }));
    const t = mk('text', { x, y: y + 3 }); t.textContent = label; svg.appendChild(t);
  };
  const edge = (x1, y1, x2, y2, i, n) => {
    const l = mk('line', { class: 'me spark', x1, y1, x2, y2, stroke: '#4f8dfd' });
    l.style.animationDelay = (i * (3.2 / n)) + 's';
    svg.appendChild(l);
  };
  if (kind === 'boss') {
    const pts = [[30, 88], [76, 88], [124, 88], [170, 88]];
    pts.forEach((p, i) => edge(100, 30, p[0], p[1] - 10, i, 4));
    node(100, 30, 'Boss', 'var(--orch)', 44);
    ['🙋', '🧑\u200d💼', '📋', '💰'].forEach((e, i) => node(pts[i][0], pts[i][1], e, Object.values(FRIENDC)[i], 30));
  } else if (kind === 'board') {
    const pts = [[30, 25], [170, 25], [30, 90], [170, 90]];
    pts.forEach((p, i) => edge(100, 57, p[0], p[1], i, 4));
    node(100, 57, 'Board', 'var(--bb)', 50);
    ['🙋', '🧑\u200d💼', '📋', '💰'].forEach((e, i) => node(pts[i][0], pts[i][1], e, Object.values(FRIENDC)[i], 30));
  } else {
    edge(52, 40, 52, 76, 0, 3); edge(70, 57, 118, 57, 1, 3); edge(140, 57, 168, 40, 2, 3);
    node(52, 30, '🙋', FRIENDC.Candidate, 28); node(52, 86, '🧑\u200d💼', FRIENDC.Manager, 28);
    node(94, 57, 'Board', 'var(--bb)', 44); node(150, 57, 'Boss', 'var(--orch)', 40);
    node(178, 30, '📋', FRIENDC.HR, 28); node(178, 86, '💰', FRIENDC.Finance, 28);
  }
}
document.querySelectorAll('.mini').forEach((svg) => buildMini(svg, svg.dataset.mini));

/* guess buttons */
document.querySelectorAll('.guessbtns button').forEach((b) => {
  b.onclick = () => {
    GUESS = b.dataset.g;
    document.querySelectorAll('.guessbtns button').forEach((x) => x.classList.remove('picked'));
    b.classList.add('picked');
  };
});

/* ---------- the race ---------- */
function goalLine() {
  const ask = Math.max(90, Math.min(400, +$('inAsk').value || 130));
  return `🎯 Goal: ONE deal all four say yes to. Ask $${ask}k vs offer $100k — where will they land? Watch…`;
}

function blankS() { return { turns: 0, wasted: 0, cost: 0, done: false, board: {}, finishedAt: null }; }

function laneHTML(e) {
  const n = NICE[e];
  const chips = CHIPS.map(([f, label]) =>
    `<span class="chip" id="chip-${e}-${f}">${label}: <b>—</b></span>`).join('');
  return `<div class="lane" style="--e:${n.cvar}" id="lane-${e}">
    <div class="lane-top"><span style="font-size:22px">${n.emoji}</span>
      <span class="lane-name">${n.name} <small>(${n.tech})</small></span>
      <span class="done-tag">🏁 Done!</span>
      <span class="lane-live"><span>Turns <b id="t-${e}">0</b></span>
        <span>Wasted <b id="w-${e}">0</b></span>
        <span>Talk cost <b id="c-${e}">$0.000</b></span></span></div>
    <div class="comm" id="bub-${e}"></div>
    <div class="lane-mid">
      <svg class="topo" id="topo-${e}" viewBox="0 0 300 150"></svg>
      <div class="trackwrap"><div class="track" id="track-${e}"></div>
        <div class="board5">${chips}</div></div>
    </div>
    <div class="talk" id="talk-${e}"></div>
  </div>`;
}

function buildTopo(e) {
  const svg = $('topo-' + e), t = TOPO[e];
  const NS = 'http://www.w3.org/2000/svg';
  const mk = (tag, attrs) => { const el = document.createElementNS(NS, tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]); return el; };
  t.edges.forEach(([a, b]) => {
    const [x1, y1] = t.nodes[a], [x2, y2] = t.nodes[b];
    svg.appendChild(mk('line', { class: 'te', x1, y1, x2, y2 }));
  });
  for (const name in t.nodes) {
    const [x, y] = t.nodes[name];
    const hub = name === 'SUP' || name === 'BB';
    const w = hub ? 72 : 68;
    const g = mk('g', { class: 'tn', id: `ng-${e}-${name}` });
    const color = name === 'BB' ? 'var(--bb)' : name === 'SUP' ? NICE[e].cvar : (FRIENDC[name] || '#888');
    g.setAttribute('style', `color:${color}`);
    g.appendChild(mk('rect', { x: x - w / 2, y: y - 13, width: w, height: 26, rx: 6, stroke: color }));
    const nm = mk('text', { class: 'nm', x, y: y - 1.5 });
    nm.textContent = name === 'BB' ? '📋 Board' : name === 'SUP' ? '👔 Boss' : `${FRIENDE[name] || ''} ${name}`;
    g.appendChild(nm);
    const val = mk('text', { class: 'val', x, y: y + 9.5, id: `nv-${e}-${name}` });
    val.textContent = hub ? 'deal: ?' : (name === 'Candidate' ? 'asks $?' : name === 'Manager' ? 'offers $?' : '…');
    g.appendChild(val);
    svg.appendChild(g);
  }
  // seed the negotiators' opening numbers
  setNodeVal(e, 'Candidate', `asks $${S[e].board.ask}k`);
  setNodeVal(e, 'Manager', `offers $${S[e].board.offer}k`);
}
function setNodeVal(e, name, text) { const el = $(`nv-${e}-${name}`); if (el) el.textContent = text; }
function setHubVal(e, text) { setNodeVal(e, 'BB', text); setNodeVal(e, 'SUP', text); }
function speak(e, name, on) { const g = $(`ng-${e}-${name}`); if (g) g.classList.toggle('speak', on); }

/* a labeled pill that travels along an edge — you SEE what is sent to whom */
function travelMsg(e, from, to, text, type) {
  const svg = $('topo-' + e); if (!svg) return;
  const t = TOPO[e]; if (!t.nodes[from] || !t.nodes[to]) return;
  const [x1, y1] = t.nodes[from], [x2, y2] = t.nodes[to];
  const NS = 'http://www.w3.org/2000/svg';
  const g = document.createElementNS(NS, 'g');
  g.setAttribute('class', 'pillg');
  const w = Math.max(30, text.length * 5.4 + 10);
  const rect = document.createElementNS(NS, 'rect');
  rect.setAttribute('width', w); rect.setAttribute('height', 14); rect.setAttribute('rx', 7);
  rect.setAttribute('fill', DOTC[type] || DOTC.msg);
  const txt = document.createElementNS(NS, 'text');
  txt.setAttribute('x', w / 2); txt.setAttribute('y', 10);
  txt.textContent = text;
  g.appendChild(rect); g.appendChild(txt);
  svg.appendChild(g);
  const t0 = performance.now(), dur = Math.max(400, Math.min(900, speed * 1.2 || 500));
  (function tick(now) {
    const k = Math.min(1, (now - t0) / dur);
    const x = x1 + (x2 - x1) * k - w / 2, y = y1 + (y2 - y1) * k - 7;
    g.setAttribute('transform', `translate(${x},${y})`);
    if (k < 1) requestAnimationFrame(tick); else setTimeout(() => g.remove(), 150);
  })(t0);
}

/* a dot that travels along an edge — the "moving arrow" */
function travelDot(e, from, to, type) {
  const svg = $('topo-' + e); if (!svg) return;
  const t = TOPO[e]; if (!t.nodes[from] || !t.nodes[to]) return;
  const [x1, y1] = t.nodes[from], [x2, y2] = t.nodes[to];
  const NS = 'http://www.w3.org/2000/svg';
  const dot = document.createElementNS(NS, 'circle');
  dot.setAttribute('r', '5'); dot.setAttribute('class', 'dot');
  dot.setAttribute('fill', DOTC[type] || DOTC.msg);
  dot.style.color = DOTC[type] || DOTC.msg;
  svg.appendChild(dot);
  const t0 = performance.now(), dur = Math.max(250, Math.min(600, speed * 1.4 || 300));
  (function tick(now) {
    const k = Math.min(1, (now - t0) / dur);
    dot.setAttribute('cx', x1 + (x2 - x1) * k);
    dot.setAttribute('cy', y1 + (y2 - y1) * k);
    if (k < 1) requestAnimationFrame(tick); else dot.remove();
  })(t0);
}

function hubOf(e, agent) {
  if (e === 'orchestrator') return 'SUP';
  if (e === 'blackboard') return 'BB';
  return (agent === 'Candidate' || agent === 'Manager' || agent === 'HR') ? 'BB' : 'SUP';
}
function hubLabel(e, agent) { return hubOf(e, agent) === 'BB' ? '📋 <b>Board</b>' : '👔 <b>Boss</b>'; }
function who(agent) { return `${FRIENDE[agent] || ''} <b>${esc(agent)}</b>`; }
const FIELDWORD = { band_max: 'the band', total_cap: 'the cap', salary: 'the deal',
                    offer: 'the offer', ask: 'the ask', bonus: 'the bonus', remote: 'remote days' };
function pretty(t) {
  return String(t).replace(/band_max|total_cap|salary|offer|bonus|remote|ask/g, (m) => FIELDWORD[m] || m)
    .replace(/\s*\(core\)/, '');
}

/* ---------- playback ---------- */
function setSpeed(ms, btn) {
  speed = ms;
  document.querySelectorAll('.speeds button').forEach((b) => b.classList.toggle('on', b === btn));
  if (timer) { stopTimer(); play(); }
}
document.querySelectorAll('.speeds button').forEach((b) => { b.onclick = () => setSpeed(+b.dataset.sp, b); });

function play() {
  if (timer) return;
  $('playbtn').textContent = '⏸ Pause';
  timer = setInterval(() => {
    if (speed === 0) { while (qTotal()) drainOne(); } else drainOne();
    maybeFinish();
  }, speed === 0 ? 40 : speed);
}
function stopTimer() { clearInterval(timer); timer = null; }
function togglePlay() {
  if (timer) { stopTimer(); $('playbtn').textContent = '▶ Play'; } else play();
}
function stepOne() { stopTimer(); $('playbtn').textContent = '▶ Play'; if (qTotal()) { drainOne(); maybeFinish(); } }

function maybeFinish() {
  if (allDoneSeen && !qTotal() && !finishedShown) {
    finishedShown = true; raceFinished = true;
    stopTimer();
    winTimer = setTimeout(showWinner, 1600);
  }
}

/* ---------- run lifecycle ---------- */
function startRace(engines) {
  if (finishedShown) {           // a spent guess must not score the next race
    GUESS = null;
    document.querySelectorAll('.guessbtns button').forEach((x) => x.classList.remove('picked'));
  }
  clearTimeout(winTimer); winTimer = null;
  raceEngines = engines.slice();
  Qs = {}; rr = 0; S = {}; allDoneSeen = false; raceFinished = false; finishedShown = false;
  const ask0 = +$('inAsk').value || 130, band = +$('inBand').value || 110;
  engines.forEach((e) => { S[e] = blankS(); S[e].board.ask = ask0; S[e].board.offer = 100; Qs[e] = []; });
  $('lanes').innerHTML = engines.map(laneHTML).join('');
  engines.forEach(buildTopo);
  $('goal').textContent = goalLine();
  go(2);
  if (es) { es.close(); es = null; }
  if (PRE) {
    PRE.events.forEach((ev) => { if (engines.includes(ev.engine)) qPush(ev); });
    allDoneSeen = true;           // the recording already contains the whole run
  } else {
    // the recording only covers the default party — other numbers replay as demo talk
    const mode = (MODE === 'cassette' &&
      (ask0 !== INFO.defaults.ask || band !== INFO.defaults.band)) ? 'mock' : MODE;
    const q = `ask=${ask0}&band=${band}&engines=${engines.join(',')}&delay=0&mode=${mode}`;
    es = new EventSource('/run?' + q);
    es.onmessage = (m) => {
      const ev = JSON.parse(m.data);
      if (ev.engine === '_meta') {
        if (ev.kind === 'all_done') { allDoneSeen = true; es.close(); es = null; }
        if (ev.kind === 'error') {
          $('liveinfo').textContent = '⚠ Something went wrong. Please try again.';
          console.error(ev.attrs && ev.attrs.msg);
        }
        return;
      }
      qPush(ev);
    };
    es.onerror = () => {
      if (es) { es.close(); es = null; }
      if (raceEngines.every((e) => S[e].done)) allDoneSeen = true;
      else $('liveinfo').textContent = '⚠ Connection lost — press "Race again".';
    };
  }
  stopTimer(); play();
}
function restartRace() { startRace(raceEngines.length ? raceEngines : ALL); }

/* ---------- event → animation ---------- */
function bump(id, val) { const el = $(id); if (el) el.textContent = val; }

/* the communication ledger: every line says WHO talks TO WHOM, with the numbers */
function say(e, html) {
  const el = $('bub-' + e); if (!el) return;
  const d = document.createElement('div');
  d.className = 'cl'; d.innerHTML = html;
  el.appendChild(d);
  while (el.children.length > 60) el.removeChild(el.firstChild);
  el.scrollTop = el.scrollHeight;
}
function narrateWrite(e, a, s, agent) {
  const to = hubLabel(e, agent);
  const from = who(agent);
  const arrow = `<span class="dir">→</span>`;
  switch (a.field) {
    case 'ask':
      setNodeVal(e, 'Candidate', `asks $${a.new}k`);
      travelMsg(e, 'Candidate', hubOf(e, 'Candidate'), `$${a.new}k`, 'write');
      return a.new === s.board.offer
        ? `${from} ${arrow} ${to}: OK — <b>$${a.new}k</b>. That is your final number. Deal! 🤝`
        : `${from} ${arrow} ${to}: ✏️ I come down — my ask is now <b>$${a.new}k</b>.`;
    case 'offer':
      setNodeVal(e, 'Manager', `offers $${a.new}k`);
      travelMsg(e, 'Manager', hubOf(e, 'Manager'), `$${a.new}k`, 'write');
      return (s.board.band_max != null && a.new === s.board.band_max)
        ? `${from} ${arrow} ${to}: ✏️ <b>$${a.new}k</b> — the top of the band. My final offer.`
        : `${from} ${arrow} ${to}: ✏️ I go up — my offer is now <b>$${a.new}k</b>.`;
    case 'band_max':
      setNodeVal(e, 'HR', `band $${a.new}k`);
      travelMsg(e, 'HR', hubOf(e, 'HR'), `band $${a.new}k`, 'write');
      return `${from} ${arrow} ${to}: ✏️ the salary band stops at <b>$${a.new}k</b>. No base pay above it.`;
    case 'total_cap':
      setNodeVal(e, 'Finance', `cap $${a.new}k`);
      travelMsg(e, 'Finance', hubOf(e, 'Finance'), `cap $${a.new}k`, 'write');
      return `${from} ${arrow} ${to}: ✏️ salary + bonus must stay under <b>$${a.new}k</b>.`;
    case 'salary':
      setHubVal(e, `deal: $${a.new}k`);
      travelMsg(e, agent, hubOf(e, agent), `deal $${a.new}k`, 'write');
      return `🤝 <b>DEAL!</b> Ask = offer = <b>$${a.new}k</b>. HR and Finance, finish the papers.`;
    case 'bonus':
      travelMsg(e, 'Finance', hubOf(e, 'Finance'), `+$${a.new}k`, 'write');
      return `${from} ${arrow} ${to}: ✏️ there is room under the cap — bonus <b>$${a.new}k</b>. Approved.`;
    case 'remote':
      travelMsg(e, 'HR', hubOf(e, 'HR'), `${a.new} days`, 'write');
      return `${from} ${arrow} ${to}: ✏️ the candidate came down a lot — <b>${a.new} remote days</b>.`;
  }
  return '';
}
function handle(ev) {
  const e = ev.engine, a = ev.attrs || {}, s = S[e];
  if (!s) return;
  switch (ev.kind) {
    case 'agent_activated': {
      travelDot(e, hubOf(e, ev.agent), ev.agent, 'msg');
      speak(e, ev.agent, true);
      const trg = a.trigger || '';
      let why = 'your turn.';
      if (trg.startsWith('seed')) why = 'the talk starts — go.';
      else if (trg.includes('changed')) why = `🔔 ${esc(pretty(trg))} — react.`;
      else if (trg.includes('sweep')) why = `your turn (${esc(trg)}).`;
      say(e, `${hubLabel(e, ev.agent)} <span class="dir">→</span> ${who(ev.agent)}: ${why}`);
      break;
    }
    case 'gen_ai.client.call.finished': {
      s.turns++; if (!a.changed) s.wasted++;
      s.cost += a.cost_usd || 0;
      bump('t-' + e, s.turns); bump('w-' + e, s.wasted);
      bump('c-' + e, '$' + s.cost.toFixed(3));
      speak(e, ev.agent, false);
      if (!a.changed) {
        say(e, `${who(ev.agent)} <span class="dir">→</span> ${hubLabel(e, ev.agent)}: ✅ nothing to change.`);
        travelDot(e, ev.agent, hubOf(e, ev.agent), 'msg');
      }
      const step = document.createElement('div');
      step.className = 'step' + (a.changed ? '' : ' noop');
      step.textContent = FRIENDE[ev.agent] || '·';
      step.title = `${ev.agent}: ` + (a.changed ? 'changed the plan' : 'nothing to change (wasted turn)');
      $('track-' + e).appendChild(step);
      if (a.message) {
        const d = document.createElement('div');
        d.className = 'm'; d.style.setProperty('--c', FRIENDC[ev.agent] || '#888');
        d.innerHTML = `<span class="w">${esc(ev.agent)}</span> ${md(a.message)}`;
        const box = $('talk-' + e); box.appendChild(d); box.scrollTop = box.scrollHeight;
      }
      break;
    }
    case 'state_write': {
      const line = narrateWrite(e, a, s, ev.agent);   // reads the OLD board (pre-write)
      s.board[a.field] = a.new;
      if (line) say(e, line);
      const chip = $(`chip-${e}-${a.field}`);
      if (chip) {
        const shown = a.field === 'cost' ? '$' + a.new : a.new;
        chip.querySelector('b').textContent = shown;
        chip.classList.remove('hit'); void chip.offsetWidth; chip.classList.add('hit');
      }
      break;
    }
    case 'agent_retriggered':
      if (e === 'blackboard' || (e === 'hybrid' && (ev.agent === 'Guests' || ev.agent === 'Budget')))
        travelDot(e, 'BB', ev.agent, 'retrig');
      say(e, `🔔 The plan changed — <b>${esc(ev.agent)}</b> must look again.`);
      break;
    case 'error':
      s.done = true; s.err = true;
      lastErr = a.msg || 'engine error';
      say(e, '⚠ Something went wrong here.');
      console.error(a.msg);
      break;
    case 'run_finished': {
      s.done = true; s.finishedAt = s.turns;
      if (a.state) for (const f in a.state) {
        const chip = $(`chip-${e}-${f}`);
        if (chip) chip.querySelector('b').textContent = f === 'cost' ? '$' + a.state[f] : a.state[f];
      }
      const flag = document.createElement('div');
      flag.className = 'step flag'; flag.textContent = '🏁🎉';
      $('track-' + e).appendChild(flag);
      $('lane-' + e).classList.add('finished');
      say(e, `🏁 <b>Done in ${s.turns} turns!</b> All four said yes.`);
      break;
    }
  }
}

/* ---------- winner scene ---------- */
function showWinner() {
  if ($('s2').classList.contains('active')) go(3);   // don't yank users who navigated away
  const ranked = raceEngines.slice().sort((x, y) => S[x].turns - S[y].turns);
  const b = S[ranked[0]].board;
  if (b.salary == null || ranked.some((e) => S[e].err)) {   // never celebrate a broken run
    $('verdict').innerHTML = '⚠ Something went wrong — the talk did not finish. Please press <b>🔁 Race again</b>.'
      + (lastErr ? `<br><small style="color:var(--mut)">detail: ${esc(lastErr).slice(0, 160)} — if this repeats, restart the server (Ctrl-C, then ./run.sh).</small>` : '');
    $('guessresult').textContent = '';
    $('podium').innerHTML = ''; $('score').innerHTML = '';
    return;
  }
  const plan = `$${b.salary}k salary + $${b.bonus}k bonus + ${b.remote} remote days`;

  if (raceEngines.length === 1) {
    const e = raceEngines[0], n = NICE[e];
    $('verdict').innerHTML = `${n.emoji} <b>${n.name}</b> closed the deal: <b>${plan}</b>.<br>
      It used <b>${S[e].turns} turns</b> (${S[e].wasted} wasted) and paid <b>$${S[e].cost.toFixed(3)}</b> for the talk.`;
    $('guessresult').textContent = '';
    $('podium').innerHTML = '';
    $('score').innerHTML = '';
    $('podium').insertAdjacentHTML('beforeend',
      `<button class="cta" onclick="startRace(['orchestrator','blackboard','hybrid'])">🏁 Now race all three!</button>`);
    return;
  }

  const win = ranked[0], lose = ranked[ranked.length - 1];
  $('verdict').innerHTML = `🎉 <b>Same deal from all three:</b> ${plan}.<br>
    ${NICE[win].emoji} <b style="color:${NICE[win].cvar}">${NICE[win].name}</b> needed only <b>${S[win].turns} turns</b>.
    ${NICE[lose].emoji} ${NICE[lose].name} needed <b>${S[lose].turns}</b>.<br>
    <b>Less talk. Same deal. That is the whole idea!</b>`;

  if (GUESS) {
    $('guessresult').innerHTML = GUESS === win
      ? `✅ Your guess was right! Great job! 🎉`
      : `❌ Good try! The winner was ${NICE[win].emoji} ${NICE[win].name}.`;
  } else $('guessresult').textContent = '';

  const heights = { 0: 150, 1: 105, 2: 72 };
  const medals = ['🥇', '🥈', '🥉'];
  const order = ranked.length === 3 ? [ranked[1], ranked[0], ranked[2]] : ranked;
  $('podium').innerHTML = order.map((e) => {
    const rank = ranked.indexOf(e);
    return `<div class="pod" style="--e:${NICE[e].cvar}">
      <div class="medal">${medals[rank]}</div>
      <div class="who">${NICE[e].emoji} ${NICE[e].name}</div>
      <div class="turns">${S[e].turns} turns</div>
      <div class="bar" data-h="${heights[rank]}"></div></div>`;
  }).join('');
  requestAnimationFrame(() => requestAnimationFrame(() => {
    document.querySelectorAll('.pod .bar').forEach((el) => { el.style.height = el.dataset.h + 'px'; });
  }));

  $('score').innerHTML = `<tr><th>Way</th><th>Turns</th><th>Wasted turns</th><th>Talk cost</th></tr>` +
    ranked.map((e) => `<tr class="${e === win ? 'win' : ''}" style="--e:${NICE[e].cvar}">
      <td class="way">${NICE[e].emoji} ${NICE[e].name}</td><td>${S[e].turns}</td>
      <td>${S[e].wasted}</td><td>$${S[e].cost.toFixed(3)}</td></tr>`).join('');

  confetti();
}

function confetti() {
  const box = $('confetti');
  const colors = ['#ff6b9d', '#4fd1c5', '#f5c542', '#4f8dfd', '#c792ea', '#63c750'];
  for (let i = 0; i < 90; i++) {
    const c = document.createElement('div');
    c.className = 'cf';
    c.style.left = Math.random() * 100 + 'vw';
    c.style.background = colors[i % colors.length];
    c.style.animationDuration = (2.2 + Math.random() * 2) + 's';
    c.style.animationDelay = (Math.random() * .8) + 's';
    box.appendChild(c);
    setTimeout(() => c.remove(), 5200);
  }
}

/* ---------- small UI ---------- */
function toggleTalk() {
  document.body.classList.toggle('showtalk');
  $('talkbtn').textContent = document.body.classList.contains('showtalk') ? '💬 Hide the talk' : '💬 Show the talk';
}
function openParty() { $('partybox').classList.toggle('open'); }
function openWords() { $('words').classList.add('open'); }
function closeWords() { $('words').classList.remove('open'); }
$('words').onclick = (ev) => { if (ev.target === $('words')) closeWords(); };
['inAsk', 'inBand'].forEach((id) => $(id).addEventListener('input', () => { $('goal').textContent = goalLine(); }));

/* expose for inline onclick= */
Object.assign(window, { go, startRace, restartRace, togglePlay, stepOne, toggleTalk, openParty, openWords, closeWords });

/* ---------- boot ---------- */
function applyInfo() {
  MODE = INFO.cassette ? 'cassette' : 'mock';
  $('liveinfo').textContent = INFO.cassette
    ? '🎙 Real AI talk — recorded. Free to watch.'
    : '🤖 Pretend AI talk — no internet needed.';
  if (INFO.version) $('liveinfo').title = 'ovb v' + INFO.version;
  if (INFO.scenario && INFO.scenario !== EXPECT_SCENARIO) {
    document.body.insertAdjacentHTML('afterbegin',
      '<div style="position:sticky;top:0;z-index:99;background:var(--bad);color:#fff;' +
      'padding:10px 16px;text-align:center;font-weight:700">⚠ The server is running OLD code ' +
      '(' + esc(INFO.scenario) + '). Stop it (Ctrl-C) and start it again: ./run.sh</div>');
  }
}
if (PRE) {
  INFO = PRE.info || INFO;
  if (INFO.defaults) { $('inAsk').value = INFO.defaults.ask; $('inBand').value = INFO.defaults.band; }
  applyInfo();
  // no server: hide things that need one
  document.querySelectorAll('.expertlink,.btnlink').forEach((el) => { el.style.display = 'none'; });
  document.querySelectorAll('[onclick*="openParty"]').forEach((el) => { el.style.display = 'none'; });
} else {
  fetch('/info').then((r) => r.json()).then((d) => { INFO = d; applyInfo(); })
    .catch(() => applyInfo());
}
playStory();

/* shareable auto-start links (also used for headless screenshots):
   /?auto=race&speed=300&ask=140&band=115  — starts the full race at that pace */
(function () {
  const q = new URLSearchParams(location.search);
  if (q.get('ask') && $('inAsk')) $('inAsk').value = q.get('ask');
  if (q.get('band') && $('inBand')) $('inBand').value = q.get('band');
  if (q.get('auto') === 'race') {
    const sp = q.get('speed');
    if (sp !== null) {
      const btn = [...document.querySelectorAll('.speeds button')].find((b) => +b.dataset.sp === +sp);
      setSpeed(+sp || 0, btn);
    }
    startRace(ALL);
  }
})();
