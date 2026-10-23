---
source: ISSUE-748
timestamp: '2026-06-04T18:29:06.824459+00:00'
title: 'EmbargoLifecycle PoC: migrate AcceptInviteToEmbargo received use case'
type: implementation
---

## Issue #748 — EmbargoLifecycle proof-of-concept: migrate AcceptInviteToEmbargo received use case

Migrated `AcceptInviteToEmbargoOnCaseReceivedUseCase` to use the new
`EmbargoLifecycle` service as the first real caller of `accept_embargo_invite`
in OBSERVED mode.

### Changes

**`vultron/core/use_cases/received/embargo.py`**

- `execute()` now delegates to `EmbargoLifecycle.accept_embargo_invite(
  transition_mode=OBSERVED)` instead of the inline state-machine manipulation
  helpers.
- Removed `_apply_received_embargo_acceptance` and
  `_record_received_embargo_acceptance` private helpers (dead code after
  migration; only called by this one use case).
- Preserves the non-standard-transition WARNING ('state-sync override') for
  backward compatibility with existing caplog tests.
- `case.record_event()` still called by the use case when the service result
  indicates case state changed (AC-4: service returns result, caller records
  event).
- Cleaned up now-unused `CaseModel` import.

### Outcome

All 24 existing AcceptInviteToEmbargo tests pass unchanged. Full suite:
2864 passed. Black, flake8, mypy, and pyright all clean.

PR: [#783](https://github.com/CERTCC/Vultron/pull/783)
