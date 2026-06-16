---
source: ISSUE-1004
timestamp: '2026-06-16T17:19:34.416179+00:00'
title: Define SvcBTTriggerBase + SvcEmbargoTriggerBase for embargo trigger use cases
type: implementation
---

## Issue #1004 — Define SvcBTTriggerBase + SvcEmbargoTriggerBase and apply to embargo trigger use cases

Introduced a two-level ABC hierarchy in
`vultron/core/use_cases/triggers/_base.py`:

- `SvcBTTriggerBase`: template method `execute()` that owns the common
  workflow — init transient state, call `_prepare()`, validate the
  `TriggerActivityPort`, construct `BTBridge`, call `_build_tree()`, run
  the BT, raise on failure, call `_handle_result()`, return activity dict.
- `SvcEmbargoTriggerBase`: extends `SvcBTTriggerBase` with a concrete
  `_handle_result()` that validates and stores the `lifecycle_result` from
  BT output, then delegates to the per-operation `_log_lifecycle_result()` hook.

All 5 embargo trigger use cases (`SvcProposeEmbargoUseCase`,
`SvcAcceptEmbargoUseCase`, `SvcRejectEmbargoUseCase`,
`SvcTerminateEmbargoUseCase`, `SvcProposeEmbargoRevisionUseCase`) were
refactored to extend `SvcEmbargoTriggerBase`, eliminating the duplicated
`__init__`, BTBridge construction, `captured`/`result_out` setup, and
`lifecycle_result` type-guard that previously appeared verbatim in every class.

Also replaced the stale 'Not every handler needs a BT: use BTs for complex
branching/state transitions; use procedural code for simple CRUD' guidance in
`.github/copilot-instructions.md` with the spec-aligned BT-15-001/BT-15-002
rule: all trigger and received use cases MUST delegate protocol-significant
behavior to a BT via `BTBridge`.

7 new hook contract tests added in `test/core/use_cases/triggers/test_base.py`.
All 3422 unit tests pass. Black, flake8, mypy, pyright clean.

PR: [#1007](https://github.com/CERTCC/Vultron/pull/1007)
