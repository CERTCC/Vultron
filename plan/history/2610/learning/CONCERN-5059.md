---
source: CONCERN-5059
timestamp: '2026-10-21T19:31:02.025810+00:00'
title: Duplicate-Accept guard reads any replication state as a completed join backfill
type: learning
---

## Summary

`CheckInviteeNotAlreadyParticipantNode` (`vultron/core/behaviors/case/nodes/invite_participant.py`) treats any `VultronReplicationState` on record for a joined invitee as proof that the join backfill ran. It refuses the Accept as a duplicate (CLP-13-001).

A replication state has other writers too:

- the embargo pause (`record_embargo_pause`, CM-10-005);
- the `Reject(CaseLedgerEntry)` ack (`UpdateReplicationStateNode`, `sync/nodes/chain.py`);
- the replay guard (`replay_guard.py`).

So a participant that was seated without a join, and that holds one of those states from an earlier act, has a later `Accept` of a stub Invite refused as a duplicate. Its consent and join effects never apply. Whether that matters depends on whether such a participant can still need the join, because a seated participant already receives the ledger by fan-out.

Found in the pre-push review of #5032.

## Question

Should the guard key on a join-specific fact (for example a join-backfill target on record) rather than on any state existing? Or is refusing every Accept from a seated participant correct?

Governing specs: CLP-13-001, CM-17-004, CM-10-005

Where: vultron/core/behaviors/case/nodes/invite_participant.py

**Resolved**: 2026-10-21 — implementation tracked in #5074.

Docs PR: <https://github.com/CERTCC/Vultron/pull/5077>.

Spec: `specs/case-management.yaml` (CM-17-012).
