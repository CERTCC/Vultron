---
source: ISSUE-712
timestamp: '2026-06-04T15:30:35.994232+00:00'
title: Move pre-BT domain work into BT nodes for engage/defer/add-note
type: implementation
---

## Issue #712 — Move pre-BT domain work into BT leaf nodes

Moved protocol-significant domain operations out of pre-BT procedural
sections in trigger use cases and into BT leaf nodes, making them
visible to BT analysis and auditing tools.

### Changes

**New BT nodes** (`vultron/core/behaviors/note/nodes.py`):

- `CreateNoteNode` — creates and persists a note via `TriggerActivityPort`,
  writes `note_id`/`note_dict` to a shared `result_out` dict
- `AttachNoteFromResultNode` — reads `note_id` from `result_out` at
  execution time and appends it to the case's `notes` list (idempotent)

**New BT factory functions**:

- `engage_case_trigger_bt()` in
  `vultron/core/behaviors/case/engage_defer_trigger_tree.py` — sequences
  `TransitionParticipantRMtoAccepted → sender_side_bt`
- `defer_case_trigger_bt()` — sequences
  `TransitionParticipantRMtoDeferred → sender_side_bt`
- `add_note_to_case_trigger_bt()` in
  `vultron/core/behaviors/note/add_note_trigger_tree.py` — sequences
  `CreateNoteNode → AttachNoteFromResultNode → sender_side_bt`

**Use case changes**:

- `SvcEngageCaseUseCase`: removed pre-BT `update_participant_rm_state`
  call; now uses `engage_case_trigger_bt()`
- `SvcDeferCaseUseCase`: removed pre-BT `update_participant_rm_state`
  call; now uses `defer_case_trigger_bt()`
- `SvcAddNoteToCaseUseCase`: removed pre-BT `factory.create_note()` and
  inline case attachment block; now uses `add_note_to_case_trigger_bt()`
  with `result_out` dict pattern

**Test fixture fixes**:

- Fixed `case_participants` not populated in `_make_case_with_case_manager`
  helpers in `test_trignotify.py` and `test_note_trigger.py` — the helpers
  only populated `actor_participant_index` but `update_participant_rm_state`
  iterates `case.case_participants`; this was a silent bug in all prior tests
- Pre-advance actor participants to `RM.VALID` so engage/defer transitions
  (`VALID → ACCEPTED`, `VALID → DEFERRED`) are state-machine-valid

**Behavior change**: engage-case with no participant record now raises
`VultronValidationError` (HTTP 422) instead of silently succeeding.
The old test `test_trigger_engage_case_no_participant_returns_202_with_warning`
was renamed and updated to assert 422.

**New BT-path tests** (`test/core/use_cases/triggers/test_case_engage_defer.py`):

- `test_engage_case_updates_rm_to_accepted_via_bt` — verifies RM.ACCEPTED
  via DataLayer re-read after execute()
- `test_defer_case_updates_rm_to_deferred_via_bt` — verifies RM.DEFERRED
- `test_add_note_creates_note_via_bt` — verifies note in result and note_id
  in `case.notes`
- `test_add_note_returns_activity_via_bt` — verifies activity dict returned
- `test_engage_case_rm_not_updated_when_no_participant` — documents failure
  semantics

All 2680 tests pass. PR: [#770](https://github.com/CERTCC/Vultron/pull/770)
