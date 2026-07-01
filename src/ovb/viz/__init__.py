"""Visualization: turn the WORM event stream into a self-contained animated HTML
report (no build step, no server). The v0.2 React/D3 live dashboard consumes the
same event contract over SSE."""
from .report import render_html

__all__ = ["render_html"]
