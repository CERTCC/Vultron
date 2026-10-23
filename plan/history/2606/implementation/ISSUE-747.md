---
source: ISSUE-747
timestamp: '2026-06-04T17:23:31.007907+00:00'
title: EmbargoLifecycle accept/reject/terminate/record_consent + OBSERVED mode
type: implementation
---

## Issue #747 — EmbargoLifecycle: add accept/reject/terminate/record_consent + OBSERVED mode

Implements the four remaining operations on the `EmbargoLifecycle` service
(child of Epic #538) and extends all five operations with full OBSERVED mode
support.

### Changes

**`vultron/core/services/embargo_lifecycle.py`**

- Refactored `propose_embargo` to use new `_drive_em_transition` private
  helper, eliminating the OBSERVED-mode `NotImplementedError`. OBSERVED now
  force-syncs to a fallback EM state instead of raising.
- Added `accept_embargo_invite`: owner-gated EM PROPOSED→ACTIVE /
  REVISE→ACTIVE; all actors receive PEC acceptance; syncs `active_embargo`
  in OBSERVED mode even when EM state was already ACTIVE.
- Added `reject_embargo_invite`: owner-gated EM PROPOSED→NO_EMBARGO /
  REVISE→ACTIVE; all actors receive PEC rejection.
- Added `terminate_active_embargo`: drives EM ACTIVE/REVISE→EXITED, clears
  `active_embargo`, cascades PEC RESET to all participants. In STRICT mode
  requires `active_embargo` to be set.
- Added `record_participant_consent`: PEC-only operation for any
  `PEC_Trigger`; used by received use cases to record a single actor's
  consent change without touching EM state.
- Private helpers added: `_drive_em_transition`, `_record_actor_pec_acceptance`,
  `_record_actor_pec_rejection`, `_cascade_pec_reset`.

**`test/core/services/test_embargo_lifecycle.py`**

- Replaced obsolete `test_propose_embargo_observed_mode_raises_not_implemented`
  with `test_propose_embargo_observed_mode_syncs_invalid_state`.
- Added 22 new boundary tests covering STRICT/OBSERVED mode, owner vs.
  non-owner, invalid EM transitions, PEC state preconditions, idempotency,
  and actor-not-in-case guard.

### Outcome

All 2817 tests pass. Black, flake8, mypy, and pyright all clean.

PR: [#781](https://github.com/CERTCC/Vultron/pull/781)
