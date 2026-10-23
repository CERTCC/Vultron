---
title: 'CA-1 + CA-3: CaseActor broadcast on case update (CM-06-001/CM-06-002)'
type: implementation
timestamp: '2026-03-25T00:00:00+00:00'
source: LEGACY-2026-03-25-ca-1-ca-3-caseactor-broadcast-on-case-update-cm
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3283
legacy_heading: 'CA-1 + CA-3: CaseActor broadcast on case update (CM-06-001/CM-06-002)'
date_source: git-blame
---

## CA-1 + CA-3: CaseActor broadcast on case update (CM-06-001/CM-06-002)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3283`
**Canonical date**: 2026-03-25 (git blame)
**Legacy heading**

```text
CA-1 + CA-3: CaseActor broadcast on case update (CM-06-001/CM-06-002)
```

**Date**: 2026-03-20
**Phase**: PRIORITY-200 (Case Actor)
**Status**: COMPLETE

### Summary

Implemented the CaseActor broadcast requirement (CM-06-001/CM-06-002):
after `UpdateCaseReceivedUseCase` saves a case update, it now emits an
`Announce` activity from the CaseActor to all active case participants.

### Changes

**`vultron/core/models/activity.py`**:

- Added `to: list[str] | None = None` and `cc: list[str] | None = None`
  addressing fields to `VultronActivity` so broadcast activities carry
  recipient information for downstream delivery routing.

**`vultron/core/ports/datalayer.py`**:

- Added `by_type(as_type: str) -> dict[str, dict]` to the `DataLayer`
  Protocol so core use cases can query objects by AS2 type without
  importing adapter-layer code.

**`vultron/core/use_cases/case.py`**:

- Added `_broadcast_case_update()` private method to
  `UpdateCaseReceivedUseCase`.
- After saving the updated case, calls `_broadcast_case_update()` which:
  1. Looks up the CaseActor via `dl.by_type("Service")` filtered by
     `context == case_id`.
  2. Collects all participant actor IDs from
     `case.actor_participant_index.keys()`.
  3. Creates a `VultronActivity(as_type="Announce", actor=case_actor_id,
     as_object=case_id, to=participant_ids)` and persists it.
  4. Appends the broadcast activity ID to the CaseActor's
`outbox.items` and saves the CaseActor.

- Broadcast also fires when the update contains only a reference (no
  fields to apply), consistent with CM-06-001 applying to any case update.

**`test/core/use_cases/test_case_use_cases.py`**:

- Added four new broadcast tests (CA-3):
  - `test_update_case_broadcasts_announce_to_participants` — happy path
  - `test_update_case_no_broadcast_when_no_case_actor` — graceful no-op
  - `test_update_case_no_broadcast_when_no_participants` — graceful no-op
  - `test_update_case_broadcast_includes_all_participants` — multi-participant

### Test results

1008 passed, 5581 subtests passed (up from 1004).

### Lessons learned

- `by_type` was already implemented on `TinyDbDataLayer` but missing from
  the `DataLayer` Protocol; adding it to the port was the minimal change
  to keep core code architecture-compliant.
- The broadcast fires even for reference-only updates (no field changes),
  since CM-06-001 does not restrict notification to field-changing updates.
- Actual HTTP delivery of the broadcast to participant inboxes requires
  the CaseActor's per-actor outbox queue to be populated and the
  `outbox_handler` to be triggered. Writing to `outbox.items` (the shared
  DL actor object) records the broadcast for history/visibility but does
  not trigger immediate delivery — consistent with the existing pattern in
  trigger use cases and `CloseCaseReceivedUseCase`.
