"""ovb — Orchestrator vs Blackboard.

A tiny, dependency-free lab that runs the *same specialist agents* over the
*same task* through two different control models:

    * orchestrator  — hub-and-spoke, supervisor-routed, isolated sub-agents.
    * blackboard    — shared-state, event-driven, agents re-trigger on writes.

The point is to make the difference *measurable*: agent calls, tokens, latency,
and a full audit log all come out of instrumentation, not hard-coded numbers.
"""

__version__ = "0.1.0"
