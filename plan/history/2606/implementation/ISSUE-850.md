---
source: ISSUE-850
timestamp: '2026-06-10T14:47:56.738399+00:00'
title: BT-15-001 audit and remediate triggers/case/ add_participant_status
type: implementation
---

## Issue #850 — Audit triggers/case/ subpackage for remaining inline SM transitions

Audited all 6 files in `vultron/core/use_cases/triggers/case/` against
BT-15-001 (trigger-side `execute()` must delegate SM transitions to BTBridge).

**Findings:**

- `engage.py`, `defer.py`: BTBridge delegation already in place ✅
- `create.py`, `add_object.py`, `add_report.py`: pure CRUD, no SM transitions
  — added BT-15-001 audit docstrings ✅
- `add_participant_status.py`: BT-15-001 violation — `ParticipantStatus`
  created with explicit `rm_state`/`vfd_state` inline in `execute()` ❌→✅

**Remediation:**

- Added `resolve_participant_state_from_dl()` module-level helper
- Added `CreateParticipantStatusNode` BT leaf node to `participant.py`
- Added `add_participant_status_trigger_bt()` factory function
- Refactored `SvcAddParticipantStatusUseCase.execute()` to use BTBridge,
  mirroring the engage/defer pattern
- Added 5 new unit tests for `CreateParticipantStatusNode`

**Lesson learned:** `dl.read()` reconstructs objects via `find_in_vocabulary`
(AS2 VOCABULARY), not `find_in_core_vocabulary` (CORE_VOCABULARY). Tests that
check `isinstance(stored, CoreParticipantStatus)` fail because the datalayer
returns the wire-layer `ParticipantStatus` subclass. Use the wire-layer type in
isinstance assertions when reading back from the datalayer.

PR: [#870](https://github.com/CERTCC/Vultron/pull/870)
