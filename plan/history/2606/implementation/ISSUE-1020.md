---
source: ISSUE-1020
timestamp: '2026-06-17T16:30:55.175479+00:00'
title: Fix EXPECTED_EVENT_TYPES legacy names + add CS-transition invariant
type: implementation
---

## Issue #1020 — Inv-5 (1/3): Fix EXPECTED_EVENT_TYPES legacy names + add CS-transition invariant

Fixed `EXPECTED_EVENT_TYPES` in `test/ci/test_case_ledger_invariants.py` to
use current `MessageSemantics` StrEnum values, replacing names that predated
the enum:

- `accept_report` → `ack_report`
- `propose_embargo` → `invite_to_embargo_on_case`
- `accept_embargo` → `accept_invite_to_embargo_on_case`
- `notify_fix_ready`, `notify_fix_deployed`, `notify_published` → collapsed
  to `add_participant_status_to_participant`
- `add_note` → `add_note_to_case`

Removed `@pytest.mark.xfail` from `test_invariant_5_expected_event_types_present`.

Added `test_invariant_15_cs_state_transitions_observed` (with
`_cs_observations_from_snap()` helper) to assert all three CS transitions
(fix_ready/VFd, fix_deployed/VFD, published/P* pxa_state) are observed in the
authoritative case-actor log. Handles both camelCase and snake_case key variants.
No production code changes were required.

PR: [#1023](https://github.com/CERTCC/Vultron/pull/1023)
