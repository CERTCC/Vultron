---
source: ISSUE-1074
timestamp: '2026-06-22T15:07:37.042102+00:00'
title: 'Add hard invariant: no execute() calls execute_with_setup() more than once'
type: implementation
---

## Issue #1074 — Add AST-based invariant test: assert no execute() method calls execute_with_setup() more than once (CLP-10-005)

Added two new tests to `test/architecture/test_single_bt_execution_received_side.py`:

- `test_no_execute_method_calls_execute_with_setup_more_than_once`: walks all
  `.py` files under `vultron/core/use_cases/` with `ast`, counts
  `execute_with_setup` call sites inside each `execute()` method (own scope
  only, not nested helpers via `_walk_own_scope`), and asserts the count is
  ≤ 1. Hard invariant — no `KNOWN_VIOLATIONS` escape hatch.

- `test_detector_catches_synthetic_multi_execute_with_setup_violation`:
  confirms the detector flags two direct calls in one `execute()` body (AC-3),
  and confirms it does NOT false-positive on a single call inside a nested
  helper function defined inside `execute()`.

Also added `_is_execute_with_setup_call` and `_walk_own_scope` helpers, and
updated the module docstring to document both the proxy ratchet and the hard
invariant.

All 3440 unit tests pass (2 new). Black, flake8, mypy, pyright clean.

PR: <https://github.com/CERTCC/Vultron/pull/1078>
