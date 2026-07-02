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
const FRIENDC = { Guests: '#6ea8fe', Budget: '#4fd1c5', Food: '#d3a6ff', Chairs: '#ff8f8f' };
const FRIENDE = { Guests: '😀', Budget: '💰', Food: '🍕', Chairs: '🪑' };
const CHIPS = [['guests', '😀 Guests'], ['max_guests', '💰 Guests we can pay'], ['cost', 'Cost $'],
               ['pizzas', '🍕 Pizzas'], ['chairs', '🪑 Chairs']];
const TOPO = {
  orchestrator: { nodes: { SUP: [150, 22], Guests: [48, 108], Budget: [116, 108], Food: [184, 108], Chairs: [252, 108] },
    edges: [['SUP', 'Guests'], ['SUP', 'Budget'], ['SUP', 'Food'], ['SUP', 'Chairs']] },
  blackboard: { nodes: { BB: [150, 70], Guests: [50, 24], Budget: [250, 24], Food: [50, 116], Chairs: [250, 116] },
    edges: [['BB', 'Guests'], ['BB', 'Budget'], ['BB', 'Food'], ['BB', 'Chairs']] },
  hybrid: { nodes: { BB: [74, 70], Guests: [34, 30], Budget: [34, 112], SUP: [188, 70], Food: [256, 42], Chairs: [256, 100] },
    edges: [['BB', 'Guests'], ['BB', 'Budget'], ['BB', 'SUP'], ['SUP', 'Food'], ['SUP', 'Chairs']] },
};
const DOTC = { msg: '#4f8dfd', write: '#2dd4bf', retrig: '#c792ea' };

/* ---------- tiny helpers ---------- */
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
const md = (s) => esc(s).replace(/^\s*#{1,6}\s*/gm, '').replace(/^\s*[-*]\s+/gm, '• ')
  .replace(/\*\*([^*]+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+?)`/g, '<b>$1</b>');

/* ---------- global state ---------- */
let INFO = { cassette: false, defaults: { guests: 15, budget: 600 } };
let MODE = 'mock';
let GUESS = null;
let raceEngines = [];
let S = {};                 // per-engine live state
let Qs = {};                // per-engine buffered event queues (drained round-robin → a real race)
let rr = 0;                 // round-robin cursor
let es = null, timer = null, speed = 900, winTimer = null;
let allDoneSeen = false, raceFinished = false, finishedShown = false;
const PRE = window.PRELOADED || null;

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
  t(300, () => { zap('cnMoney'); $('ca1').classList.add('pulse'); });
  t(1300, () => { zap('cnGuests'); flipTo('chG', '12'); });                 // money cuts the list
  t(2300, () => { $('ca1').classList.remove('pulse'); $('ca2').classList.add('pulse'); });
  t(3100, () => { zap('cnPizzas'); flipTo('chP', '4'); });                  // the list sets the numbers
  t(3700, () => { zap('cnChairs'); flipTo('chC', '12'); });
  t(4900, () => { $('ca2').classList.remove('pulse'); });
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
    ['😀', '💰', '🍕', '🪑'].forEach((e, i) => node(pts[i][0], pts[i][1], e, Object.values(FRIENDC)[i], 30));
  } else if (kind === 'board') {
    const pts = [[30, 25], [170, 25], [30, 90], [170, 90]];
    pts.forEach((p, i) => edge(100, 57, p[0], p[1], i, 4));
    node(100, 57, 'Board', 'var(--bb)', 50);
    ['😀', '💰', '🍕', '🪑'].forEach((e, i) => node(pts[i][0], pts[i][1], e, Object.values(FRIENDC)[i], 30));
  } else {
    edge(52, 40, 52, 76, 0, 3); edge(70, 57, 118, 57, 1, 3); edge(140, 57, 168, 40, 2, 3);
    node(52, 30, '😀', FRIENDC.Guests, 28); node(52, 86, '💰', FRIENDC.Budget, 28);
    node(94, 57, 'Board', 'var(--bb)', 44); node(150, 57, 'Boss', 'var(--orch)', 40);
    node(178, 30, '🍕', FRIENDC.Food, 28); node(178, 86, '🪑', FRIENDC.Chairs, 28);
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
  const want = Math.max(1, Math.min(50, +$('inGuests').value || 15));
  const cap = Math.max(1, +$('inBudget').value || 600);
  const g = Math.min(want, Math.floor(cap / 50));
  return `🎯 Goal: the best party the money can buy — ${g} guests · $${g * 50} · ${Math.ceil(g / 3)} pizzas · ${g} chairs`;
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
    <div class="bubble" id="bub-${e}">The friends will start to talk…</div>
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
    const w = name === 'SUP' ? 66 : name === 'BB' ? 56 : 48;
    const g = mk('g', { class: 'tn' });
    const color = name === 'BB' ? 'var(--bb)' : name === 'SUP' ? NICE[e].cvar : (FRIENDC[name] || '#888');
    g.appendChild(mk('rect', { x: x - w / 2, y: y - 9, width: w, height: 18, rx: 5, stroke: color }));
    const txt = mk('text', { x, y: y + 3.2 });
    txt.textContent = name === 'BB' ? 'Board' : name === 'SUP' ? 'Boss' : name;
    g.appendChild(txt);
    svg.appendChild(g);
  }
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
  return (agent === 'Guests' || agent === 'Budget') ? 'BB' : 'SUP';
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
  const want = +$('inGuests').value || 15, cap = +$('inBudget').value || 600;
  engines.forEach((e) => { S[e] = blankS(); S[e].board.guests = want; Qs[e] = []; });
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
      (want !== INFO.defaults.guests || cap !== INFO.defaults.budget)) ? 'mock' : MODE;
    const q = `guests=${want}&budget=${cap}&engines=${engines.join(',')}&delay=0&mode=${mode}`;
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

/* the narrator: ONE short, simple sentence per event, made from the real numbers */
function say(e, html) {
  const el = $('bub-' + e); if (!el) return;
  el.innerHTML = html;
  el.classList.remove('say'); void el.offsetWidth; el.classList.add('say');
}
function narrateWrite(e, a, s) {
  const cap = +$('inBudget').value || 600;
  const g = s.board.guests;
  switch (a.field) {
    case 'cost':
      return a.new > cap
        ? `💰 <b>Budget:</b> ${g} guests cost <b>$${a.new}</b>. That is too much! We only have $${cap}.`
        : `💰 <b>Budget:</b> now it costs <b>$${a.new}</b>. That fits our $${cap}! ✅`;
    case 'max_guests':
      return `💰 <b>Budget:</b> the money is enough for <b>${a.new} guests</b>, not more.`;
    case 'guests':
      return `😀 <b>Guests:</b> OK, I cut the list — <b>${a.old} → ${a.new} guests</b>.`;
    case 'pizzas':
      return `🍕 <b>Food:</b> ${g} guests need <b>${a.new} pizzas</b> (1 pizza for 3 guests).`;
    case 'chairs':
      return `🪑 <b>Chairs:</b> ${g} guests need <b>${a.new} chairs</b> — one for each person.`;
  }
  return '';
}
function handle(ev) {
  const e = ev.engine, a = ev.attrs || {}, s = S[e];
  if (!s) return;
  switch (ev.kind) {
    case 'agent_activated':
      travelDot(e, hubOf(e, ev.agent), ev.agent, 'msg');
      say(e, `${FRIENDE[ev.agent] || '🎤'} <b>${esc(ev.agent)}</b> is thinking…`);
      break;
    case 'gen_ai.client.call.finished': {
      s.turns++; if (!a.changed) s.wasted++;
      s.cost += a.cost_usd || 0;
      bump('t-' + e, s.turns); bump('w-' + e, s.wasted);
      bump('c-' + e, '$' + s.cost.toFixed(3));
      if (!a.changed) say(e, `✅ <b>${esc(ev.agent)}:</b> all good. Nothing to change.`);
      const step = document.createElement('div');
      step.className = 'step' + (a.changed ? '' : ' noop');
      step.textContent = FRIENDE[ev.agent] || '·';
      step.title = `${ev.agent}: ` + (a.changed ? 'changed the plan' : 'nothing to change (wasted turn)');
      $('track-' + e).appendChild(step);
      if (a.changed) {
        const core = e !== 'orchestrator' && hubOf(e, ev.agent) === 'BB';
        travelDot(e, ev.agent, hubOf(e, ev.agent), core ? 'write' : 'msg');
      }
      if (a.message) {
        const d = document.createElement('div');
        d.className = 'm'; d.style.setProperty('--c', FRIENDC[ev.agent] || '#888');
        d.innerHTML = `<span class="w">${esc(ev.agent)}</span> ${md(a.message)}`;
        const box = $('talk-' + e); box.appendChild(d); box.scrollTop = box.scrollHeight;
      }
      break;
    }
    case 'state_write': {
      const line = narrateWrite(e, a, s);   // uses the OLD board (e.g. guest count before a cut)
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
      s.done = true;
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
      say(e, `🏁 <b>Done in ${s.turns} turns!</b> The plan fits the money.`);
      break;
    }
  }
}

/* ---------- winner scene ---------- */
function showWinner() {
  if ($('s2').classList.contains('active')) go(3);   // don't yank users who navigated away
  const ranked = raceEngines.slice().sort((x, y) => S[x].turns - S[y].turns);
  const b = S[ranked[0]].board;
  const plan = `${b.guests} guests, $${b.cost}, ${b.pizzas} pizzas, ${b.chairs} chairs`;

  if (raceEngines.length === 1) {
    const e = raceEngines[0], n = NICE[e];
    $('verdict').innerHTML = `${n.emoji} <b>${n.name}</b> found the party: <b>${plan}</b>.<br>
      It used <b>${S[e].turns} turns</b> (${S[e].wasted} wasted) and paid <b>$${S[e].cost.toFixed(3)}</b> for the talk.`;
    $('guessresult').textContent = '';
    $('podium').innerHTML = '';
    $('score').innerHTML = '';
    $('podium').insertAdjacentHTML('beforeend',
      `<button class="cta" onclick="startRace(['orchestrator','blackboard','hybrid'])">🏁 Now race all three!</button>`);
    return;
  }

  const win = ranked[0], lose = ranked[ranked.length - 1];
  $('verdict').innerHTML = `🎉 <b>Same party from all three:</b> ${plan}.<br>
    ${NICE[win].emoji} <b style="color:${NICE[win].cvar}">${NICE[win].name}</b> needed only <b>${S[win].turns} turns</b>.
    ${NICE[lose].emoji} ${NICE[lose].name} needed <b>${S[lose].turns}</b>.<br>
    <b>Less talk. Same party. That is the whole idea!</b>`;

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
['inGuests', 'inBudget'].forEach((id) => $(id).addEventListener('input', () => { $('goal').textContent = goalLine(); }));

/* expose for inline onclick= */
Object.assign(window, { go, startRace, restartRace, togglePlay, stepOne, toggleTalk, openParty, openWords, closeWords });

/* ---------- boot ---------- */
function applyInfo() {
  MODE = INFO.cassette ? 'cassette' : 'mock';
  $('liveinfo').textContent = INFO.cassette
    ? '🎙 Real AI talk — recorded. Free to watch.'
    : '🤖 Pretend AI talk — no internet needed.';
}
if (PRE) {
  INFO = PRE.info || INFO;
  if (INFO.defaults) { $('inGuests').value = INFO.defaults.guests; $('inBudget').value = INFO.defaults.budget; }
  applyInfo();
  // no server: hide things that need one
  document.querySelectorAll('.expertlink,.btnlink').forEach((el) => { el.style.display = 'none'; });
  document.querySelectorAll('[onclick*="openParty"]').forEach((el) => { el.style.display = 'none'; });
} else {
  fetch('/info').then((r) => r.json()).then((d) => { INFO = d; applyInfo(); })
    .catch(() => applyInfo());
}
playStory();
