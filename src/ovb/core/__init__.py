"""Core kernel: typed state + reducer, registry, gate, LLM clients, trace, and
the Harness base class. Domain-agnostic — it never imports `ovb.domain` except
through injected objects."""
