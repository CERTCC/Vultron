---
source: ISSUE-519
timestamp: '2026-06-04T14:28:48.308544+00:00'
title: Resolve all ARCH-01-001 core→wire import violations
type: implementation
---

## Issue #519 — Resolve all ARCH-01-001 core→wire import violations

Removed the three remaining `vultron.wire` imports from `vultron/core/`,
completing ARCH-01-001 compliance with zero known violations.

### Files fixed

- **`vultron/core/behaviors/report/nodes.py`** — removed `rm_engage_case_activity`
  / `rm_defer_case_activity` imports; `EmitEngageCaseActivity` and
  `EmitDeferCaseActivity` now delegate to `TriggerActivityPort.engage_case` /
  `defer_case` and return `FAILURE` if the port is not injected.
- **`vultron/core/use_cases/received/actor.py`** — removed deferred inline import
  of `announce_vulnerability_case_activity`; `_emit_announce_case` now calls
  `self._trigger_activity.announce_vulnerability_case`.
- **`vultron/core/use_cases/received/note.py`** — removed top-level import of
  `add_note_to_case_activity`; `_broadcast_note_to_participants` delegates to
  `self._trigger_activity.add_note_to_case` and skips if port is absent.

### Supporting changes

- **`TriggerActivityPort`** — added `announce_vulnerability_case(case_id, actor,
  context_id, to) -> str` method.
- **`TriggerActivityAdapter`** — implemented `announce_vulnerability_case` via
  DataLayer read + `announce_vulnerability_case_activity` factory.
- **`inbox_handler.py`** — moved `ADD_NOTE_TO_CASE` from `_SYNC_PORT_SEMANTICS`
  to `_SYNC_AND_TRIGGER_PORT_SEMANTICS`; added `DEFER_CASE`, `ENGAGE_CASE`, and
  `VALIDATE_REPORT` to `_TRIGGER_ACTIVITY_PORT_SEMANTICS`.
- **`ValidateReportReceivedUseCase`**, **`ValidateCaseUseCase`**,
  **`EngageCaseReceivedUseCase`**, **`DeferCaseReceivedUseCase`** — accept
  optional `trigger_activity` and thread it through to `BTBridge`.
- Architecture ratchet test — `KNOWN_VIOLATIONS` cleared to `frozenset()`.
- Test fixtures updated in `test_prioritize_tree.py`, `test_validate_tree.py`,
  `test_actor.py`, `test_note.py`, and `test_report.py`.

### Outcome

2574 tests pass, 12 skipped. mypy and pyright both report zero issues.

PR: [#762](https://github.com/CERTCC/Vultron/pull/762)
