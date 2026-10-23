---
signal: concern
source: CONCERN-2040
timestamp: '2026-08-27T17:15:29.609244+00:00'
title: test/metadata spec-dump invocations dominate full-suite time
type: learning
---

## Summary

`test/metadata/` accounts for ~27.7 s of the ~170 s full-suite wall-clock.
The root cause is repeated `spec-dump` / YAML parse invocations: the
`test_real_specs` and `test_docs_render` tests each call `spec-dump` or
load the full YAML registry independently (~2.4 s × 4 render tests plus
the decision-audit inventory setup).

This is a separate root cause from the AST-walking ratchets addressed in
issues #2020 and #2038, and warrants its own investigation.

## Analysis (2026-08-27)

`load_registry()` takes ~1.5 s first call (YAML parse + Pydantic validation of
2,851 specs) and ~0.5 s on subsequent calls (OS disk cache). The real-corpus loads
in the default suite:

- `test_docs_render.py::test_render_for_kind_real_registry_produces_output`
  (parametrized 4×, calls `load_registry()` inline per invocation)
- `test_real_specs.py::real_registry` (module-scoped fixture) + `lint()` +
  `main_llm_json()` = 3 loads in that module
- `test_coverage.py::test_compute_real_registry_has_nonzero_coverage` = 1 load

**Fix**: add a session-scoped `real_registry` fixture at `test/metadata/conftest.py`
shared across the full `test/metadata/specs/` package. Also add optional
`registry: SpecRegistry | None = None` parameter to `lint()` so the test can
pass the cached instance.

Session fixture is preferred over the module-level import-time cache pattern used
in `test/architecture/_corpus.py` because `load_registry()` takes ~1.5 s (comfortably
within the 5 s per-test budget) while the architecture corpus cold-parse took ~2.3 s
(too close to the margin).

**Resolved**: 2026-08-27 — implementation tracked in #2757.
