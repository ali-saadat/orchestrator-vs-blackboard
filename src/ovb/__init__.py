"""ovb — Orchestrator vs Blackboard vs Hybrid.

Three agent-**harness** topologies over the *same* agents, the *same* task, and
the *same* deterministic gate. Only the control loop differs. Everything is
instrumented (calls, tokens, cost, latency, an append-only WORM event log) so the
comparison is measured, not asserted.

Read `docs/HARNESS.md` for the organizing idea: a multi-agent system is
`agents + a harness`, and orchestrator / blackboard / hybrid are three harnesses.
"""

__version__ = "0.4.1"
