#!/usr/bin/env bash
#
# One-click launcher for the ovb live dashboard.
#
#   ./run.sh            open the live dashboard in your browser
#   ./run.sh --lan      also serve on your local network (share it, no tunnel)
#   ./run.sh bench      run the CLI benchmark instead of the dashboard
#   ./run.sh models     compare models (cheapest vs pricier) from the cassette
#
# Prefers `uv` (fast, zero-setup). Falls back to a local .venv + pip on first run.
set -eo pipefail
cd "$(dirname "$0")"

# Default to `serve`. If the user passed only flags (e.g. --lan), still run `serve`.
if [ "$#" -eq 0 ]; then
  set -- serve
elif [ "${1#-}" != "$1" ]; then
  set -- serve "$@"
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run ovb "$@"
fi

PY="${PYTHON:-python3}"
if [ ! -d .venv ]; then
  echo "▶ first run: creating .venv and installing (needs internet) …"
  "$PY" -m venv .venv
  ./.venv/bin/python -m pip install -q --upgrade pip
  ./.venv/bin/python -m pip install -q -e .
fi
exec ./.venv/bin/ovb "$@"
