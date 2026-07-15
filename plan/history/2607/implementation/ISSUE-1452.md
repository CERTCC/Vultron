---
source: ISSUE-1452
timestamp: '2026-07-15T20:07:41.112285+00:00'
title: Implement VulnerabilityCase staged types
type: implementation
---

## Issue #1452 — Implement VulnerabilityCase staged types (IncomingReport → Case → EmbargoedCase)

Implements ADR-0033 lifecycle-staged domain types for `VulnerabilityCase` as three Pydantic
subclasses — `IncomingReport`, `Case`, `EmbargoedCase` — each enforcing its field-set invariants
via `@model_validator(mode="after")`. All three share `type_="VulnerabilityCase"` (inherited,
not redeclared) so DataLayer round-trip is preserved without a stored discriminator (LST-05-003).

### What was built

- **`vultron/core/models/staged_case.py`** (new, 160 lines): Three staged types with
  `ConfigDict(from_attributes=True)` enabling `model_validate`-at-edge promotion from a
  parent `VulnerabilityCase` instance (LST-05-001). None register in `CORE_VOCABULARY`
  (guarded by `CoreObject.__init_subclass__`).
- **`test/core/models/test_staged_case.py`** (new, 393 lines, 38 tests): Full coverage of
  AC-1–AC-6 and LST-02-001 through LST-05-003 including DataLayer round-trip and a
  regression test for string-only `case_statuses`.

### Key implementation decisions

- `ConfigDict(from_attributes=True)` on each staged subclass is required by Pydantic v2 to
  accept a parent-class instance in `model_validate`. Without it, Pydantic v2 rejects
  non-dict/non-same-class inputs.
- `Case._check_case_invariants` uses `any(isinstance(s, CaseStatus) for s in self.case_statuses)`
  rather than a truthy check — a string-only list is truthy but has no materialized `CaseStatus`
  and would fail on `current_status` access downstream.
- The `except ValueError` in `EmbargoedCase._check_embargoed_invariants` re-raises with a
  message that accurately says "no materialized CaseStatus" (not "wrong em_state"), separating
  the two distinct failure modes.
- `EmbargoedCase` inherits from `Case` (not directly from `VulnerabilityCase`) so the Case
  invariants (≥2 participants, ≥1 report, materialized status) are enforced first via MRO
  validator ordering.

### Validation

- 4816 unit tests pass (pre-PR: 4815 + 1 new regression test)
- Black, flake8, mypy, pyright all clean
- Pre-PR code review at high effort: 2 CONFIRMED correctness bugs fixed, 2 PLAUSIBLE
  findings deferred (noted as PR advisory comment)

PR: <https://github.com/CERTCC/Vultron/pull/1473>
