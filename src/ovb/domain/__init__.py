"""The swappable scenario layer. A new scenario is a new `domain/` module that
provides an initial state, a gate predicate, and a `build_registry()`. The kernel
and engines never change."""
