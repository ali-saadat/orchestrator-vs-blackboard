"""Run the task through the ORCHESTRATOR and print its trace.

    python demos/run_orchestrator.py           # mock, deterministic
    python demos/run_orchestrator.py --real     # real Claude calls
"""
import argparse

import _bootstrap  # noqa: F401
from ovb import orchestrator, task, viz
from ovb.llm import get_llm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true", help="use the Anthropic API")
    ap.add_argument("--model", default="claude-sonnet-5")
    args = ap.parse_args()

    print(task.SCENARIO, "\n")
    result = orchestrator.run(get_llm(args.real, args.model), real=args.real)
    print(viz.render_trace(result))


if __name__ == "__main__":
    main()
