PY ?= python3
export PYTHONPATH := $(CURDIR)/src

.PHONY: help install test serve bench orchestrator blackboard hybrid real doctor lint clean

help:
	@echo "make install     editable install (pip install -e '.[dev,real]')"
	@echo "make serve       LIVE side-by-side dashboard (real-time, full visibility)"
	@echo "make test        deterministic smoke tests (no network)"
	@echo "make bench       run all 3 harnesses (mock) + comparison + output/report.html"
	@echo "make orchestrator|blackboard|hybrid   run one harness, print its trace"
	@echo "make real        run bench against the live Claude API (needs ANTHROPIC_API_KEY)"
	@echo "make doctor      show execution mode + dependency availability"
	@echo "make clean       remove caches and generated reports"

install:
	$(PY) -m pip install -e ".[dev,real]"

test:
	$(PY) -m pytest -q

serve:
	$(PY) -m ovb serve

bench:
	$(PY) -m ovb bench

orchestrator:
	$(PY) -m ovb run orchestrator

blackboard:
	$(PY) -m ovb run blackboard

hybrid:
	$(PY) -m ovb run hybrid

real:
	$(PY) -m ovb bench --real

doctor:
	$(PY) -m ovb doctor

lint:
	ruff check src tests || true

clean:
	rm -rf .pytest_cache **/__pycache__ output/report.html output/*.jsonl
