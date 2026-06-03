---
source: ISSUE-724
timestamp: '2026-06-03T21:04:54.041048+00:00'
title: CoreObject base hierarchy + ADR-0017 for domain/wire separation
type: implementation
---

## Issue #724 — Refactor #699 step 1: core base hierarchy + ADR for domain/wire object separation

Step 1 of the larger refactor tracked in #699. Foundation only — no per-type
migrations land here. Establishes a parallel core class hierarchy in
`vultron/core/models/` that mirrors `as_Base` / `as_Object` in the wire layer,
plus the ADR capturing the parallel-hierarchy decision.

### Delivered

- `CoreObject` base class in `vultron/core/models/base.py`, inheriting from
  `VultronObject`, adding the JSON-LD `@context` field (`context_`, defaulted
  to `None` so wire-layer projection supplies the AS2 namespace), and
  auto-registering concrete subclasses in `CORE_VOCABULARY` via
  `__init_subclass__`. Registration is gated on `type_` being overridden with
  a non-union annotation, and is resolved through `typing.get_type_hints` so
  the check is robust under `from __future__ import annotations` (PEP 563).
- `CORE_VOCABULARY` registry plus `find_in_core_vocabulary()` helper in
  `vultron/core/models/registry.py`.
- ADR-0017 (`docs/adr/0017-domain-wire-object-separation.md`) capturing:
  parallel-hierarchy decision, refs-are-wire-only rule (with parent/child
  case-cycle exception called out explicitly), and the wire-style naming
  convention (`VulnerabilityCase`, not `VultronCase`).
- 12 new tests in `test/core/models/test_core_object.py`, including a PEP 563
  regression test using a real importable module file.
- Existing `Vultron*` core stubs untouched (AC-4); positively asserted in
  tests.

### Validation

- black + flake8 clean.
- mypy: `Success: no issues found in 654 source files`.
- pyright: `0 errors, 0 warnings, 0 informations`.
- pytest: `2631 passed, 12 skipped, 216 deselected, 5633 subtests passed`.
- mkdocs `--strict` warning count unchanged vs baseline (16 → 16).

### Pre-PR code review

Caught one [BLOCKING] correctness issue: the original `__init_subclass__`
implementation pattern-matched `cls.__dict__["__annotations__"]` and would
silently register every subclass under `from __future__ import annotations`
because raw annotations are strings. Switched to `typing.get_type_hints(cls)`
and added a regression test that creates a real module file (necessary
because `__future__` directives only take effect on compiled module files,
and `get_type_hints` needs proper module globals to resolve `Literal`).

PR: <https://github.com/CERTCC/Vultron/pull/734>
