---
source: CONCERN-3282
timestamp: '2026-09-17T11:33:53.590706+00:00'
title: CLP-07-003 enforcement was dormant before ADR-0088 and cannot express the requirement
  now
type: learning
---

## What happened

CLP-07-003 requires that `payloadSnapshot.actor` preserve the original asserting
actor's identity. Before ADR-0088 the CASE_MANAGER's identity and role were one
thing — any identity check was also a role check. After ADR-0088 (authority is
`CVDRole.CASE_MANAGER`, not a name or URL), the same actor may hold the
CASE_MANAGER role and simultaneously participate in the case as reporter, finder,
or coordinator.

The enforcement code in `_validate_canonical_entry` (commit boundary, `chain.py`)
checked: *if snapshot_actor == case_actor_id AND signature not in
_CASE_AUTHORED_SIGNATURES → reject.* For 11 of the 27 canonical signatures — all
participant-role activities the CASE_MANAGER-as-participant can legitimately assert
(e.g. `Add(Note)`, `Offer(EmbargoEvent)`, `Accept(EmbargoEvent)`) — this
incorrectly raises `VultronCanonicalEntryError`. The bug was filed from a code
review of PR #3290 ("Complete ADR-0088") where a partial fix was tried and
reverted.

## Root cause

The commit boundary (`_validate_canonical_entry`) receives only the already-built
snapshot. It does not receive the inbound activity's original `actor_id` — the
only information that could distinguish "CASE_MANAGER acting as participant" from
"something wrongly substituted the CASE_MANAGER's identity". The `actor_id`
parameter in `_validate_canonical_entry` is the committing actor (the CASE_MANAGER
itself), not the inbound sender.

## Resolution

Move the CLP-07-003 identity check to `lifecycle.CommitCaseLedgerEntryNode`
(`vultron/core/behaviors/case/nodes/lifecycle.py`), where `activity.actor_id` (the
original sender) is available alongside the snapshot. The check becomes:
`snapshot["actor"] MUST equal activity.actor_id`. For the CASE_MANAGER-as-
participant case, their own identity matches as sender and snapshot actor — no
false positive. For a substitution bug, the mismatch is caught.

The `actor_id` and `case_actor_id` parameters in `_validate_canonical_entry` and
the `_find_case_actor_id` lookup in `chain.py` become dead code and are removed.
`_CASE_AUTHORED_SIGNATURES` is retained — still needed for CLP-12-002.

## Outcome

- Docs PR: <https://github.com/CERTCC/Vultron/pull/3301>
- Impl issue: #3302 (blocked on #3282 and PR #3290)
- CLP-07-003 statement, rationale, and verification updated in `specs/case-ledger-processing.yaml`
- Pitfall note added to `notes/case-ledger-authority.md`

## What to watch for

**Never put CLP-07-003's identity check at the commit boundary.** The commit
boundary cannot distinguish the sender's legitimate self-assertion from
substitution because `_validate_canonical_entry` does not receive the inbound
`actor_id`. The check belongs one layer up, in `lifecycle.CommitCaseLedgerEntryNode`,
before the snapshot is handed off to the chain layer.
