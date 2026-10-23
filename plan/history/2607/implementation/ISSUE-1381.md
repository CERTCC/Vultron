---
source: ISSUE-1381
timestamp: '2026-07-15T14:35:10.625151+00:00'
title: add SpecKind.DEV_PROCESS coverage and enum-completeness assertion
type: implementation
---

## Issue #1381 — test: add SpecKind.DEV_PROCESS coverage and enum-completeness assertion (SR-02-005)

Added three tests to `test/metadata/specs/test_schema.py` covering `SpecKind.DEV_PROCESS`
and the six-tier enum completeness requirement from SR-02-005:

- `test_spec_kind_contains_exactly_six_tiers`: AC-2 canary asserting `set(SpecKind)` equals
  the exact six-value set required by SR-02-005.
- `test_dev_process_kind_round_trip`: AC-1 parametrized round-trip through `StatementSpec`,
  `SpecGroup`, and `SpecFile` with `kind=SpecKind.DEV_PROCESS`.
- `test_load_registry_dev_process_kind`: AC-3 integration smoke test loading a `kind:
  dev-process` YAML spec via `load_registry` and asserting `get_effective_kind` and
  `spec.priority`.

All 4727 unit tests pass (5 new). Black, flake8, mypy, pyright clean.

PR: <https://github.com/CERTCC/Vultron/pull/1435>
