---
source: ISSUE-435
timestamp: '2026-05-05T19:52:03.241139+00:00'
title: Implement CM-14 canonical case initialization sequence
type: implementation
---

## Overview

Implemented the CM-14 canonical case initialization sequence in the
`ReceiveReportCaseBT` behavior tree.

## Problem

The BT was executing `InitializeDefaultEmbargoNode` before
`CreateCaseOwnerParticipant`, violating CM-14-002. Additionally, neither the
case owner nor the reporter was being seeded as `PEC.SIGNATORY` after
embargo initialization, violating CM-14-003 and CM-14-005.

## Changes

### `receive_report_case_tree.py`

Swapped `CreateCaseOwnerParticipant` and `InitializeDefaultEmbargoNode` in
the BT sequence so the owner participant exists before the embargo is
initialized (CM-14-002).

### `nodes.py`

- Added `_seed_owner_as_signatory()` method to `InitializeDefaultEmbargoNode`:
  reads the owner participant from the datalayer after embargo creation and
  sets `embargo_consent_state = PEC.SIGNATORY` (CM-14-003).
- Added reporter SIGNATORY seeding in `CreateCaseParticipantNode.update()`:
  when an active embargo exists at participant-creation time, the reporter
  participant is seeded as `PEC.SIGNATORY` (CM-14-005).

### `test_receive_report_case_tree.py`

Added 3 new tests covering AC-1 through AC-5:

- `test_tree_owner_participant_precedes_embargo_in_sequence`
- `test_owner_seeded_as_signatory_after_embargo_init`
- `test_reporter_seeded_as_signatory_when_active_embargo`

## Key insight

The datalayer round-trips `VultronParticipant` to `CaseParticipant` (wire
type) on read-back. Used `hasattr()` guard instead of `isinstance` and
`cast(Any, ...)` to satisfy pyright — consistent with the existing
`_queue_participant_add_notification` pattern.

## References

- Issue: #435
- PR: #443
- Specs: CM-14-002, CM-14-003, CM-14-005, CM-14-007
