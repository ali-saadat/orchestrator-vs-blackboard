# When to use which — a decision guide

Both models use the same agents; picking between them is about **how the work is
shaped**, not how smart the agents are. This guide is the practitioner's summary;
`docs/RESEARCH.md` has the cited, in‑depth version.

## The 10‑second answer

- **Reach for an ORCHESTRATOR when the work is a *tree*:** decompose → route to
  isolated workers → aggregate. Steps are independent or strictly ordered.
- **Reach for a BLACKBOARD when the work is a *graph*:** sub‑results depend on each
  other and a change in one should immediately affect others (cross‑checks,
  constraint satisfaction, iterative refinement).

If you can draw the task as a clean top‑down flowchart, orchestrate it. If you keep
drawing arrows *back up* the chart, you want a blackboard.

## Orchestrator wins when…

| Signal | Why |
| --- | --- |
| **Routing / dispatch** ("which specialist handles this ticket?") | One decision, then a hand‑off. A hub is the natural shape. |
| **Independent parallel tool calls** (fan‑out search, N summaries) | Workers don't need each other; isolation is a feature, not a cost. |
| **Linear pipelines** (extract → transform → validate → write) | Fixed order *is* the algorithm. |
| **Strict control & auditability of *routing*** | The supervisor is a single, inspectable decision point. |
| **Cost predictability** | Roster × rounds is easy to bound and reason about. |
| **You want the simplest thing that works** | Fewer moving parts; the dominant framework default (supervisor / handoffs). |

Canonical fit: **Anthropic's orchestrator‑worker research system** (a lead agent
spins up isolated searchers and synthesizes), customer‑support routers, and most
"supervisor" / "handoff" examples in LangGraph, the OpenAI Agents SDK, AutoGen, and
CrewAI.

## Blackboard wins when…

| Signal | Why |
| --- | --- |
| **Interdependent checks / cross‑verification** (the "Step‑9 cross‑checks" case) | Agent B's finding should immediately re‑open Agent A's work. A hub would re‑sweep everyone. |
| **Constraint satisfaction / reconciliation** (the demo task) | Changing one variable ripples; you want to re‑run only what's affected. |
| **Iterative refinement toward a fixpoint** | Converge by reacting to writes, not by fixed rounds. |
| **Emergent problem solving** (opportunistic, no fixed plan) | Whichever agent can contribute next, does — the blackboard's original 1970s use case. |
| **Heavy shared context** | One shared state beats re‑passing context into every fresh sub‑agent window. |
| **You need a full write‑level audit trail** | The WORM log is the design, not an add‑on. |

Canonical fit: multi‑constraint planning/scheduling, document/code review where
findings interact, verification pipelines, and anything where "a write should wake
its dependents."

## The counter‑argument (read this before you build multi‑agent anything)

More agents is not more better. Two widely‑cited cautions:

- **Cognition — "Don't Build Multi‑Agents."** Fragmented context and implicit
  decisions across agents cause incoherent results; often a single agent with good
  context management beats a multi‑agent system.
- **Anthropic — multi‑agent research system.** Multi‑agent shines for
  breadth‑first, parallelizable search, but it **burns ~15× the tokens of a single
  chat** and only pays off when the task value justifies that.

Practical rule: **start with one agent.** Add a *topology* only when you have a
concrete reason — parallelism (→ orchestrator) or interdependence (→ blackboard) —
and can measure the win (this repo is a template for measuring it).

## A checklist

Answer these about *your* task:

1. **Do sub‑results depend on each other?**
   - No → orchestrator. · Yes → keep going.
2. **Should one agent's output *immediately* change another's, before the run ends?**
   - No (a final merge is fine) → orchestrator. · Yes → blackboard.
3. **Is there a fixed, known order of steps?**
   - Yes → orchestrator (pipeline). · No / it depends on intermediate results → blackboard.
4. **Do you need a write‑level audit trail and a deterministic stop condition?**
   - Nice‑to‑have → either. · Required → blackboard with a **gate + control unit**
     (the bounded blackboard).
5. **Is token cost or latency your binding constraint on an interdependent task?**
   - Then measure both here — the blackboard usually avoids the orchestrator's
     whole‑roster re‑sweeps.

## Hybrids (the common real answer)

Production systems are rarely pure. Frequent shapes:

- **Orchestrator of blackboards** — a supervisor routes to sub‑teams, each of which
  is a bounded blackboard internally (route at the top, react within a team).
- **Blackboard with a supervisor knowledge‑source** — a shared state where one
  privileged agent does high‑level scheduling/prioritization.
- **Bounded blackboard** — the reactive shared‑state model with a deterministic
  control unit + gate so it terminates predictably and stays auditable. This is the
  model the demo's `blackboard.py` implements, and the safest way to get the
  shared‑state benefits in production.

## 2026 nuances (before you pick either)

The research pass ([RESEARCH.md](RESEARCH.md)) surfaced four things that reshape this
decision for a 2026 reader:

1. **Reasoning models partially substitute for fan‑out.** Multi‑agent's edge is
   largely that it *spends more tokens* (token usage explained ~80% of the variance
   in Anthropic's eval). A single reasoning agent with a large thinking budget now
   absorbs work that used to justify parallel sub‑agents. Treat multi‑agent as an
   *escalation*, not a default. (RESEARCH §11 · "Reasoning Models and the Economics Shift".)
2. **There's a third topology.** Moderated **group‑chat / debate / society‑of‑mind**
   (AutoGen GroupChat, consensus/voting) is a distinct family — neither pure hub nor
   pure board. (RESEARCH §8, §11.)
3. **The protocol substrate biases the shape.** **MCP** is intrinsically
   hub‑and‑spoke (favors orchestrators); **A2A** is peer messaging (wires either, but
   gives you no native blackboard — you must add a broker/shared‑state layer).
   (RESEARCH §11 · "Protocol Substrate".)
4. **Security differs by topology.** A poisoned entry on a *shared* board can
   re‑trigger many agents (injection amplification); message‑passing contains blast
   radius better. Weigh this for untrusted inputs. (RESEARCH §12.)
