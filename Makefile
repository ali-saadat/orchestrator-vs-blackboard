PY ?= python3
export PYTHONPATH := $(CURDIR)

.PHONY: help test demo orchestrator blackboard bench real html clean

help:
	@echo "make test          run the deterministic smoke tests (no network)"
	@echo "make demo          alias for 'make bench'"
	@echo "make orchestrator  run the task through the orchestrator only"
	@echo "make blackboard    run the task through the blackboard only"
	@echo "make bench         run BOTH and print the comparison + write output/report.html"
	@echo "make real          run the benchmark against the live Claude API (needs ANTHROPIC_API_KEY)"
	@echo "make clean         remove caches and generated reports"

test:
	$(PY) tests/test_smoke.py

orchestrator:
	$(PY) demos/run_orchestrator.py

blackboard:
	$(PY) demos/run_blackboard.py

bench demo:
	$(PY) demos/benchmark.py

real:
	$(PY) demos/benchmark.py --real

clean:
	rm -rf __pycache__ */__pycache__ .pytest_cache output/report.html
