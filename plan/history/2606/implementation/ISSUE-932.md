---
source: ISSUE-932
timestamp: '2026-06-16T16:24:23.667240+00:00'
title: Normalize ParticipantStatus context to case URI at report→case promotion
type: implementation
---

## Issue #932 — Normalize ParticipantStatus context to case URI at report→case promotion

Implemented CLP-07-007: `ParticipantStatus.context` must use the case URI
once a case exists. Before this fix, three RM-transition BT nodes and
`_get_or_create_accepted_status` created status records with
`context=report_id` even after a case had been promoted, violating the
canonical ledger context invariant.

**Changes:**

- `rm_transitions.py`: `TransitionRMtoValid/Invalid/Closed` now call
  `find_case_by_report_id()` before constructing `ParticipantStatus`;
  use `case.id_` as context when available (fallback: `report_id`).
- `common.py`: `_get_or_create_accepted_status()` performs the same
  lookup; adds AC-3 backfill — updates `existing.context` from
  `report_id` → `case_id` when a case has since been promoted.
- `protocols.py`: Adds `is_participant_status_model()` TypeGuard helper
  that checks `type_ == "ParticipantStatus"` structurally so it works
  for both the core model and the wire-layer type returned by the
  DataLayer vocabulary registry.
- `participant_add.py`: Switches `isinstance(…, ParticipantStatus)` guard
  to `is_participant_status_model()` for the same reason.

**Tests:** 5 new AC-2 tests in `test_rm_transitions.py` (context = case URI
for each transition + fallback), AC-3 backfill test in `test_participant_add.py`.

**Verification:** 3397 passed, 0 failed (unit suite).

PR: [#1002](https://github.com/CERTCC/Vultron/pull/1002)
