---
source: NOTES-case-ledger-authority--clp-07-003-actor-identity-check
timestamp: '2026-09-17T17:14:23.063064+00:00'
title: CLP-07-003 Actor-Identity Check Must Live at the Receive Pipeline
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,c) delivered PR #3313; durable pitfall retained inline
**Superseded by:** vultron/core/behaviors/case/nodes/lifecycle.py; ISSUE-3282

---

## CLP-07-003 Actor-Identity Check Must Live at the Receive Pipeline, Not the Commit Boundary

*Issue #3282; implemented by PR #3313.*

CLP-07-003 requires that `payloadSnapshot.actor` equal the original asserting
actor's identity. A guard was originally placed at `_validate_canonical_entry`
(the commit boundary inside `chain.py`), checking whether `snapshot_actor ==
case_actor_id` for non-CASE_AUTHORED signatures. ADR-0088 made this check
incorrect by granting authority through role (`CVDRole.CASE_MANAGER`) rather
than identity: a holder of that role may simultaneously participate as a
reporter, finder, or coordinator, and may legitimately assert any
participant-role activity — `Add(Note)`, `Offer(EmbargoEvent)`, etc.

The commit boundary lacks the context to distinguish legitimate
CASE_MANAGER-participant self-assertion from substitution: `_validate_canonical_entry`
receives only the already-built snapshot and does not know the original inbound
`actor_id`. Eleven payload signatures (every signature in
`_CANONICAL_PAYLOAD_SIGNATURES` that is not in `_CASE_AUTHORED_SIGNATURES`) were
incorrectly rejected as false positives.

**The correct enforcement point is `lifecycle.CommitCaseLedgerEntryNode`
(`vultron/core/behaviors/case/nodes/lifecycle.py`)**, where `activity.actor_id`
(the original sender) is still available alongside the snapshot. The check is:
`snapshot["actor"] MUST equal activity.actor_id`. A mismatch is a substitution;
the CASE_MANAGER's own identity in `payloadSnapshot.actor` is never a mismatch
when they are the sender.

Pitfall: do not restore the identity comparison to `_validate_canonical_entry`.
`_CASE_AUTHORED_SIGNATURES` is still needed there for CLP-12-002's native-init
coverage check — do not delete it, only remove its use in the identity comparison.

Also remove the now-dead `actor_id` and `case_actor_id` parameters from
`_validate_canonical_entry` and the corresponding `_find_case_actor_id` lookup
in `chain.py` (confirmed dead after the block removal).
