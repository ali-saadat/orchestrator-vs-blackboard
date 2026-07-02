# Teaching guide — explaining the three ways in class

_A lesson plan for presenting orchestrator vs blackboard vs hybrid with this repo's
job-offer demo. Every trace below is real (from `ovb run <engine>`); every number is
reproducible offline (`./run.sh`, Cassette mode)._

---

## 1. The 60-second setup (say this first)

> "A company wants to hire Sam. **Four people must say yes to one deal**: the Candidate
> wants a high salary (asks $130k), the Manager wants to pay less (offers $100k), HR has
> a hard salary band, and Finance caps the total pay. They negotiate step by step.
> Here's the interesting part: **all three ways of running this conversation reach the
> exact same deal — $110k + $8k bonus + 4 remote days.** The only difference is *how
> much talking it takes*. So the question of this class is not 'which gets a better
> answer' — it's **'which wastes the least coordination?'** That's the question you'll
> face every time you build a multi-agent system."

Key framing: the agents are identical in all three ways. Only the **conversation
protocol** — who speaks when, and where information lives — changes.

## 2. The three journeys (narrated, with the real traces)

### 👔 The Boss Way (Orchestrator) — 24 turns, 10 wasted

**The metaphor**: a chairperson runs the meeting from an agenda. Nobody speaks unless
called on. Nobody hears anyone else — everything is reported to the boss, who calls the
next person.

**The journey** (point at the ledger: every line is `Boss → person` or `person → Boss`):

| Sweep | What happens | Waste |
|---|---|---|
| 1 | Boss polls all 4 in order: Candidate concedes to $126k · Manager raises to $104k · HR announces the band ($110k) · Finance announces the cap ($124k) | — |
| 2–4 | Boss polls all 4 again, three times: the two negotiators keep conceding ($123→$121→$119 vs $107→$109→$110)… **but HR and Finance are polled every round and have nothing to say** | 6 wasted turns |
| 5 | Candidate accepts $110k · Manager writes the deal · HR grants 4 remote days · Finance signs the $8k bonus | — |
| 6 | Boss polls all 4 one last time — nobody changes anything. **This whole lap exists only so the boss can *know* it's finished.** | 4 wasted turns |

**The two teaching points**:
1. **Idle polling** — the boss can't know who has something to say, so it asks everyone,
   every round. HR and Finance sit in 6 pointless meetings.
2. **The confirmation lap** — with no shared state, "are we done?" costs one full sweep
   of no-ops. Students can *see* both on the track: the faded chips.

### 📋 The Whiteboard Way (Blackboard) — 14 turns, 0 wasted

**The metaphor**: everyone stands around one whiteboard. You write your number on the
board; **the board wakes up exactly the people who care about what changed** — nobody
else.

**The journey** (real trace):

| Turn | Who → what | Why they woke up |
|---|---|---|
| 1–4 | Kickoff: Candidate $126k · Manager $104k · HR posts the band ($110k) · Finance posts the cap ($124k) | the meeting starts — everyone speaks once |
| 5–10 | Candidate and Manager **ping-pong**: $123 ↔ $107 · $121 ↔ $109 · $119 ↔ $110 | each write to the board wakes **only the other negotiator** |
| 11 | Candidate: "OK — $110k, your final number. Deal! 🤝" | the offer hit the band |
| 12 | Manager writes **the deal** on the board | ask == offer |
| 13–14 | HR wakes (grants 4 remote days) · Finance wakes (signs the $8k bonus) | **they subscribed to "the deal"** — the board woke them exactly once, exactly when relevant |

**The teaching point**: HR and Finance were silent through the entire haggle and woke
up precisely when the salary landed. **Work is proportional to what actually changes**,
not to (people × rounds). Zero wasted turns.

### 🤝 The Mix Way (Hybrid) — 13 turns, 0 wasted

**The metaphor**: you already *know* who the real negotiation is between. So you put
the live negotiation (Candidate, Manager, and HR — the referee whose band shapes the
deal) around the whiteboard, and let Finance simply **sign once at the end**.

**The journey**: turns 1–12 are the same reactive haggle as the whiteboard (minus
Finance's kickoff turn), then one supervisor call: "Finance — here's the deal, sign it"
— Finance announces the cap *and* signs the bonus in a single turn.

**The teaching point**: the hybrid wins by **encoding knowledge the architect already
has** — that Finance doesn't participate in the haggle. That's its price of admission:
you must know the coupling structure in advance. If you're wrong (Finance's cap
actually needed to shape the haggle), the hybrid breaks. (Try it: HR *must* be in the
core — the band arrives mid-negotiation. Move HR to the tail and the deal would violate
the band.)

## 3. The differences in practice — same scenario, three protocols

| | 👔 Boss Way | 📋 Whiteboard Way | 🤝 Mix Way |
|---|---|---|---|
| Who decides who speaks | the boss, fixed order | **the data** — a write wakes its subscribers | the board inside the core; the boss for the tail |
| Where the state lives | in the boss's head (agents see only what they're told) | on **one shared board** everyone reads | shared board for the core; handed to the tail |
| How change spreads | wait for your next turn in the rotation | **immediately**, to exactly the right people | immediately within the core; once, at the end, to the tail |
| How it knows it's done | a full lap where nobody changes anything | a deterministic check after every write | the core drains, then the tail finishes |
| Turns here | **24** (10 wasted) | **14** (0 wasted) | **13** (0 wasted) |
| Real cost here (Haiku) | $0.031 | $0.018 | $0.015 |
| What it costs you as a designer | nothing — simplest to build and reason about | you must design the board schema + subscriptions | you must *know* the coupling structure in advance |
| Failure mode | the hub is a bottleneck and single point of failure; cost scales with people × rounds | a badly wired board can loop or race (needs caps + a deterministic gate) | a wrong core/tail split gives wrong answers, not just slow ones |

And the one-liner for the whiteboard's win: **the orchestrator pays per person per
round; the blackboard pays per change.** In a negotiation, changes are concentrated in
two people — so the boss's bill is bigger for the identical deal.

## 4. When to use which (the take-home slide)

**Start with one agent.** If a single model call with good context does the job, every
one of these topologies is overhead. Multi-agent is an escalation, not a default.

**Choose the Boss Way (orchestrator) when the work is a *tree*:**
- routing / triage — "which specialist handles this ticket?"
- independent parallel work — fan out 5 research questions, merge the answers
- fixed pipelines — extract → transform → validate → report
- when audit/control is the priority: one visible decision point, easy human sign-off
- *Objective it serves*: predictability, governance, simplicity.

**Choose the Whiteboard Way (blackboard) when the work is a *graph*:**
- results depend on each other — one agent's finding must immediately re-open another's work
- iterative refinement to a fixpoint — negotiation, reconciliation, constraint solving
- cross-checking — a reviewer's discovery re-triggers the affected writers, not everyone
- when you need a write-level audit trail (the board's log) and token efficiency at scale
- *Objective it serves*: reactivity, efficiency on interdependent work.

**Choose the Mix Way (hybrid) when you can *see* the split:**
- a tightly-coupled core (the negotiation, the design loop) plus independent
  downstream steps (sign-offs, formatting, notification)
- *Objective it serves*: blackboard efficiency where it pays, orchestrator simplicity
  where coupling doesn't exist. Most production systems that "graduate" from a pure
  orchestrator land here.

**The heuristic to write on the board**: *draw the task as a flowchart. If the arrows
only point down, orchestrate. If you keep drawing arrows back up, you want a
blackboard. If exactly one cluster has the up-arrows, mix.*

## 5. Classroom playbook

1. **Scene 1–2 on the projector** (2 min): the story + the three ways. Then run the
   **guess game** — hands up per way. (Most rooms pick the Whiteboard; the Mix winning
   by one turn sparks the best discussion: "why did knowing the structure beat pure
   reactivity?")
2. **Run the Boss Way solo first** at Normal speed (1 min): let them *feel* the
   idle polling — "watch HR get asked again… and again."
3. **Race all three** (1 min at Fast): the wasted-turn chips pile up in lane 1 only.
4. **The winner scene**: same deal, 24 vs 14 vs 13 — then flip to the score table.
5. **Expert view** for technical audiences: the comparison table, the WORM log, modes.

**Discussion questions that work:**
- Why did the Boss Way need a whole final lap of no-ops? (No shared state ⇒ "done" must be *observed*.)
- What breaks if we move HR to the hybrid's tail? (The band arrives after the haggle ⇒ the deal violates it. Run it mentally — coupling misjudged = wrong answer.)
- Why does every way reach the *same* deal? (The concession rules are clamped to a fact-derived target — decisions are deterministic; only scheduling differs. In real systems you must *design* for this or accept divergence.)
- When would the Boss Way *win*? (Independent subtasks: 4 agents that never affect each other — the blackboard's re-trigger machinery buys nothing, and the orchestrator can parallelize the fan-out.)
- What's the security difference? (A poisoned write on a shared board re-triggers many agents; message-passing contains the blast radius.)

**Common student questions:**
- *"Is the blackboard always better?"* No — it costs board-schema design, needs loop
  caps and a deterministic done-check, and on independent work it degenerates to the
  orchestrator without the simplicity. This demo's task is chosen to be interdependent.
- *"Do the agents really talk simultaneously?"* No — on today's frameworks everything
  is turn-based. The blackboard's edge is *reactive scheduling + shared state*, not
  literal parallelism.
- *"Who decides when it's finished?"* Code, never the model: a deterministic gate
  checks "ask == offer == salary, inside band and cap." That's a production best
  practice worth teaching on its own.
