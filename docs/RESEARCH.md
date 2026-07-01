# SOTA & best practices — Orchestrator vs Blackboard multi‑agent control

> ⏳ **This document is being generated** by a multi‑agent research pass (6 parallel
> web‑research dimensions → adversarial fact‑check → gap‑fill → synthesis). When it
> lands it will replace this placeholder with a cited survey. The skeleton below is
> the intended structure.

## Contents (planned)

1. **Executive summary** — the core distinction and why it drives tokens,
   auditability, and fit.
2. **The orchestrator pattern** — mechanics; SOTA implementations (LangGraph
   supervisor & hierarchical teams, OpenAI Agents SDK / Swarm handoffs, Microsoft
   AutoGen & Magentic‑One, CrewAI hierarchical process, Anthropic orchestrator‑worker,
   Amazon Bedrock multi‑agent collaboration, Google ADK); strengths, weaknesses,
   token/latency behavior.
3. **The blackboard pattern** — origins (Hearsay‑II, BB1, HASP/SIAP; Nii 1986); the
   modern LLM revival (shared state, event‑driven, re‑triggering); relation to
   BSP/Pregel supersteps + reducers and stigmergy.
4. **Head‑to‑head** — control flow, state sharing, tokens, latency, determinism,
   auditability, SPOF, scalability, mid‑task adaptivity (with a comparison table).
5. **When to use each** — decision criteria, worked case studies, the
   "don't build multi‑agents" counter‑argument.
6. **Best practices & SOTA (2024–2026)** — observability/tracing, guardrails, control
   units & iteration caps, WORM logging, reducers/barrier syncs, evaluation, cost
   control, human‑in‑the‑loop, deterministic gates; the **bounded blackboard**.
7. **How to showcase it** — what makes a fair side‑by‑side demo; the design decisions
   behind this repo.
8. **References.**

In the meantime, [WHEN-TO-USE.md](WHEN-TO-USE.md) and [architecture.md](architecture.md)
already cover the practical decision and the implementation.
