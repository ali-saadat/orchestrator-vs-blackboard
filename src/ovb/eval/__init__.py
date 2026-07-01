"""Evaluation: the run harness (single + N-run) and the fairness contract."""
from .compare import FairnessContract, render_comparison
from .runner import run_all, run_engine

__all__ = ["run_engine", "run_all", "FairnessContract", "render_comparison"]
