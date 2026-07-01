"""Run the SAME task through BOTH control models and compare.

    python demos/benchmark.py                  # mock, deterministic
    python demos/benchmark.py --real            # real Claude calls
    python demos/benchmark.py --html out.html   # also write an HTML report

Writes output/report.html by default so you get a shareable visual artifact.
"""
import argparse
import os

import _bootstrap  # noqa: F401
from ovb import blackboard, orchestrator, task, viz
from ovb.llm import get_llm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true", help="use the Anthropic API")
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--html", default="output/report.html",
                    help="path for the HTML report (empty string to skip)")
    args = ap.parse_args()

    llm = get_llm(args.real, args.model)
    print(task.SCENARIO, "\n")

    orch = orchestrator.run(llm, real=args.real)
    bb = blackboard.run(llm, real=args.real)

    print(viz.render_trace(orch))
    print()
    print(viz.render_trace(bb))
    print(viz.render_comparison(orch, bb))

    if args.html:
        os.makedirs(os.path.dirname(args.html) or ".", exist_ok=True)
        with open(args.html, "w", encoding="utf-8") as fh:
            fh.write(viz.render_html(orch, bb, task.SCENARIO))
        print(f"\n  HTML report → {args.html}")


if __name__ == "__main__":
    main()
