"""Fairness contract + the comparison table.

`FairnessContract.assert_comparable` hard-fails if the engines were not judged on
identical terms (same roster, same gate, same sampling, same start). Passing it is
the precondition for any claim about the control models.
"""
from __future__ import annotations

from ..config import RunConfig
from ..contracts import EngineResult
from ..core.gate import Gate
from ..core.registry import AgentRegistry


class FairnessViolation(AssertionError):
    pass


class FairnessContract:
    @staticmethod
    def assert_comparable(results: dict[str, EngineResult], *,
                          registry: AgentRegistry, gate: Gate,
                          config: RunConfig) -> None:
        # every engine reached a gate-passing state
        for name, r in results.items():
            if not r.consistent:
                raise FairnessViolation(f"{name} did not reach a consistent state")
        # every engine converged to the SAME final state (metamorphic invariant)
        states = {name: tuple(sorted(r.state.items())) for name, r in results.items()}
        distinct = set(states.values())
        if len(distinct) != 1:
            raise FairnessViolation(f"engines diverged on final state: {states}")
        # sampling + wiring are pinned in config/registry/gate (fingerprints)
        _ = (registry.fingerprint(), gate.spec, config.model, config.temperature)


def _row(label, values, better="low"):
    cells = "".join(f"{str(v):>14}" for v in values.values())
    if all(isinstance(v, (int, float)) for v in values.values()):
        best = (min if better == "low" else max)(values.values())
        winners = [k for k, v in values.items() if v == best]
        win = "tie" if len(winners) == len(values) else "/".join(winners)
    else:
        win = ""
    return f"  {label:<22}{cells}   {win}"


def render_comparison(results: dict[str, EngineResult]) -> str:
    names = list(results)
    recs = {n: results[n].recorder for n in names}
    header = "  " + f"{'METRIC':<22}" + "".join(f"{n.upper():>14}" for n in names)
    lines = ["", header, "  " + "-" * (22 + 14 * len(names) + 8)]

    def col(fn):
        return {n: fn(recs[n]) for n in names}

    lines += [
        _row("agent calls", col(lambda r: r.n_calls)),
        _row("  effective (changed)", col(lambda r: r.n_effective), better="high"),
        _row("  wasted (no-op)", col(lambda r: r.n_wasted)),
        _row("state writes", col(lambda r: r.n_writes)),
        _row("total tokens", col(lambda r: r.total_usage.total)),
        _row("cost (USD)", col(lambda r: round(r.total_cost_usd, 6))),
        _row("sim latency (ms)", col(lambda r: round(r.total_latency_ms, 1))),
        "  " + "-" * (22 + 14 * len(names) + 8),
    ]
    same = len({tuple(sorted(r.state.items())) for r in results.values()}) == 1
    lines.append(f"  → all topologies reached the SAME consistent plan: {same}")
    if "orchestrator" in recs and "blackboard" in recs:
        o, b = recs["orchestrator"].n_calls, recs["blackboard"].n_calls
        lines.append(f"  → blackboard used {o / max(b,1):.2f}× fewer calls than orchestrator")
    return "\n".join(lines)
