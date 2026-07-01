# Contributing

Thanks for looking! This is a small, dependency-light lab — easy to hack on.

## Setup

```bash
./run.sh doctor            # bootstraps the environment (uv or a local .venv)
# or:
pip install -e ".[dev]"    # editable install with dev tools
```

## Workflow

- **Tests must stay green and deterministic** (no network): `make test` (10 tests).
  The mock LLM makes runs reproducible; the headline result is asserted
  (orchestrator 12 / blackboard 7 / hybrid 5, same final build).
- **Lint/format:** `ruff check src tests` (config in `pyproject.toml`).
- Keep the base install **stdlib-only for the dashboard** — heavy deps (`anthropic`,
  `fastapi`) are opt-in extras.

## Where things live

- Change the **scenario** → `src/ovb/domain/task.py` + `agents.py` (+ `core/state.py`
  fields, the tests' `EXPECTED`, the UI labels in `viz/live.py`, and re-record the
  cassette). See [docs/HANDOVER.md](docs/HANDOVER.md) §8.
- Add a **control model** → subclass `core/harness.py`'s `Harness`, implement `run()`,
  register it in `engines/__init__.py`.
- The **concept** is documented in [docs/HARNESS.md](docs/HARNESS.md).

## Conventions

- Single-author commits (no AI-attribution trailers).
- Never commit `.env` (it's gitignored) or any API key.
