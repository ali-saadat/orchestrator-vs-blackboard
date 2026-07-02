<!--
  MEDIUM POST — ready to paste into the Medium editor. No images by design.
  Suggested tags: AI Agents, Multi-Agent Systems, Enterprise AI, Software Architecture, Generative AI
-->

# Supervisor vs. Blackboard: Choosing the Right Multi-Agent AI Coordination Architecture for the Enterprise

### Two coordination patterns that predate LLMs by decades still determine whether a multi-agent system can be audited, costed, and changed in production.

## What a multi-agent architecture actually is

Most of what I know about multi-agent systems comes from putting them into production at banks, insurers, health systems and manufacturers — and then operating them long enough to watch what breaks.

A single AI agent runs into predictable limits. Its context window fills, and reasoning quality degrades as it does. One prompt cannot hold deep expertise in credit policy, fraud typologies and document extraction at the same time. And on long chains of tool calls, small per-step error rates compound into unacceptable ones. A multi-agent system addresses these limits by dividing the work: a set of specialized agents — each with a narrow role, its own tools and its own context — plus a coordination layer that decides who works, when, and how their outputs combine.

Teams concentrate their effort on model selection and prompt tuning. In practice, the coordination model is the architecture decision that determines whether the system survives production: it governs cost, latency, auditability and failure behavior to a degree that prompt-level choices cannot.

## The two approaches

Strip away the framework branding and most production topologies reduce to, or compose from, two patterns that predate large language models by decades: centralized orchestration, in which a supervisor assigns and collects work, and shared-state coordination, in which agents watch and write to a common blackboard. (Peer-to-peer handoffs and negotiation-based coordination exist, but they are the exceptions in enterprise deployments.) [Anthropic's guidance on building effective agents](https://www.anthropic.com/engineering/building-effective-agents) describes the first as orchestrator-workers; the second originates in the [blackboard systems](https://en.wikipedia.org/wiki/Blackboard_system) of 1970s–80s AI research and has been rediscovered, largely without attribution, by the event-driven agent frameworks of the past two years.

## The supervisor: governance by design

A central coordinator receives the objective, decomposes it into tasks, routes each task to a specialist agent, evaluates what comes back, and aggregates the results. Control flow is explicit: it lives in the supervisor's plan. Specialists never communicate directly; everything passes through the hub. Structurally, it is a stage-gate process with an automated gatekeeper.

The strengths align directly with what a risk function requires. Control paths are explicit and inspectable: the space of possible routes can be drawn before execution and verified from the trace afterwards — and made fully deterministic where routing is rule-based rather than model-decided. Every decision passes through one component, which gives a single natural point to instrument for end-to-end traceability, and a single choke point at which to sanitize inputs and enforce policy. Human checkpoints fall naturally between steps: pause before funds move, or before a denial goes out. Cost is boundable: with iteration caps and a fixed roster of specialists, the per-request envelope can be estimated and enforced.

The limitations are structural, not incidental. The coordinator is a throughput bottleneck and a single point of failure. Every hand-off adds a round of latency and an extra model invocation; naive implementations also re-read the accumulated context at each routing decision, though prompt caching and state summarization blunt that cost. Context concentrates at the hub, and the hub's context window becomes the binding constraint. When reality deviates from the plan, replanning falls on the same bottleneck — and hard-coded orchestrations stall outright. One lesson from operating these systems: an LLM supervisor's routing decisions are not deterministic, and they drift across model upgrades. Production deployments need routing evaluations and rule-based fallbacks on high-stakes paths.

The trade, stated plainly: you are buying governance and predictability, and paying in latency, token overhead and flexibility.

## The blackboard: coordination without a script

The blackboard inverts the premise. The current state of the problem lives in a shared workspace that every agent can read and write. Specialist agents subscribe to the parts of that state relevant to their function and activate when a relevant change appears; their contributions land back on the board, which may in turn activate others. There is no pre-scripted sequence — although the classic blackboard systems (HEARSAY-II most famously) retained a thin control component to arbitrate which triggered specialist runs next. What disappears is the script, not all arbitration.

The strengths mirror the supervisor's weaknesses. Concurrency is unplanned rather than planned: independent specialists react in parallel as the picture develops. Control coupling is loose: a specialist is added or retired by registering or removing a subscription, not by rewiring a flow — though every specialist remains coupled through the board's schema, so changing the state representation touches all subscribers. With event-driven triggers, compute tracks actual events rather than orchestration rounds; polling loops and model-evaluated triggers forfeit that economy. The pattern fits problems whose solution path cannot be specified before execution.

The costs deserve equal precision. The board's history is a complete, ordered record of what happened — essentially event sourcing — so the audit weakness is not the absence of a record but ex-ante certifiability: you cannot show in advance what the system will do, which is a hard conversation with a certification body. The real engineering work is twofold, and routinely underestimated. First, trigger and subscription design: poorly specified triggers produce contention and activation cascades, with agents repeatedly re-triggering one another without converging. Second, state consistency: versioned, append-only board entries and an explicit conflict-resolution policy for when two specialists post contradictory findings. Shared state also concentrates security and privacy exposure — any writer can, in effect, place content into every subscriber's context, so a board carrying regulated data needs write validation and data segregation. And where regulation requires named human checkpoints, contributions can be held as quarantined hypotheses pending approval, or the board's output can feed a human work queue rather than act autonomously.

The trade: you are buying adaptability and scale, and paying in explainability and control.

## Head-to-head

| Attribute | Supervisor | Blackboard |
|---|---|---|
| Control flow | Explicit; lives in the coordinator's plan | Emergent; driven by state changes |
| Communication | Hub-and-spoke; all traffic through the coordinator | Indirect, through shared state (publish/subscribe) |
| State | Concentrated in the coordinator's context | Externalized on the shared board |
| Agent activation | Assigned by the coordinator | Triggered by relevant state changes, under thin arbitration |
| Parallelism | Planned fan-out; planning and merging serialize at the hub | Unplanned; independent specialists react concurrently |
| Auditability | Single natural point to instrument; route space enumerable in advance | Complete ex-post record; weak ex-ante certifiability |
| Failure containment | Hub is a single point of failure; worker failures are visible and retryable | No single control point, but the board is a critical dependency; failures can propagate through state |
| Security posture | One choke point to sanitize inputs and enforce policy | Every writer is a potential injection vector; write validation is mandatory |
| Cost profile | Boundable with iteration caps; coordination overhead on every round | Tracks events; cascade-driven spikes unless activation limits are enforced |
| Best-fit work shape | Known process, fixed sequence, formal sign-offs | Unknown ordering, streaming events, an evolving picture |

## Where each pattern fits

The choice is rarely about the sector; it is about the shape of the work, and the same institution usually needs both. In event-heavy domains, the blackboard operates as a reasoning layer over existing event infrastructure — correlation engines, outage management, forecasting systems — synthesizing across signals those systems already produce, not replacing them.

| Sector | Objective | Better fit | Why |
|---|---|---|---|
| Banking | KYC and loan origination | Supervisor | Regulators expect a named sequence of checks with evidence at every gate |
| Banking | Post-authorization fraud investigation and case assembly | Blackboard | Signals arrive unpredictably and specialists build on each other's findings; the sub-second authorization decision itself remains with incumbent real-time models |
| Insurance | Claims adjudication | Supervisor | Fixed adjudication stages with reserved human sign-off; appealed decisions require a clean trace |
| Insurance | Catastrophe response | Blackboard | Event ordering is unknowable in advance; exposure, weather and triage specialists react as data lands |
| Healthcare | Prior authorization | Supervisor | Payer criteria form a fixed sequence, and every determination must be explainable line by line |
| Healthcare | Care-team workflow on patient events | Blackboard | Vitals and labs arrive as events; agents assemble summaries and route notifications — decision support, deliberately short of autonomous clinical judgment |
| Manufacturing | Quality and compliance documentation | Supervisor | Certification demands a repeatable, documented inspection sequence |
| Manufacturing | Supply-chain disruption response | Blackboard | Disruptions cascade across suppliers with no plannable path; sourcing, logistics and planning react in parallel |
| Retail / e-commerce | Peak-season demand and inventory response | Blackboard | Cross-channel signals arrive continuously and out of order; agents synthesize over existing forecasting systems |
| Legal / professional services | Contract review and due diligence | Supervisor | Partner accountability demands a defined review sequence and documented sign-off |

## What I advise in practice

Three questions settle most architecture reviews. Can you specify the process before execution? If yes, orchestrate. Will an auditor, a regulator or opposing counsel ask why the system did what it did? If yes, the supervisor's explicit trace is worth its overhead. Do events arrive unpredictably, with the answer assembling itself from many partial signals? Then the blackboard earns its complexity.

Mature deployments are usually hybrid: an orchestrated core owns the regulated path — the decisions that must be sequenced, checkpointed and signed off — while event-driven components sit at the perimeter, watching streams and feeding the core. Start with the simplest architecture that meets the requirement; a well-instrumented supervisor, or a single agent with good tools, is the right first system more often than not.

Whichever pattern you choose, three disciplines are non-negotiable in production. Instrument from the first day: propagated trace IDs, per-agent token and latency accounting, and alerting on activation cascades. Enforce hard limits: per-run token budgets, activation caps, and a kill switch. And treat change management as part of the architecture: pin model and prompt versions per agent, gate every upgrade behind regression evaluations, and budget for re-certification when a model change shifts routing behavior.

Model choices change quarterly. The coordination architecture is the decision the system lives with.

---

*Both patterns — plus a hybrid — run the same task with measured token cost in this open-source reference implementation: [orchestrator-vs-blackboard](https://github.com/ali-saadat/orchestrator-vs-blackboard).*
