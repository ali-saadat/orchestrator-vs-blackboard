"""Tiny stdlib .env loader (no dependency). Loads KEY=VALUE lines into the
environment for keys not already set, so `--real` picks up ANTHROPIC_API_KEY
from a local, gitignored `.env`."""
from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
