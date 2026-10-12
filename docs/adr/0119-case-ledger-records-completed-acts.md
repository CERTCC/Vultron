---
status: proposed
date: 2026-10-02
created: 2026-10-02
updated: 2026-10-02
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; specs/sync-ledger-replication.yaml SYNC-09-002;
  specs/sync-behavior-trees.yaml SBT-04-004; specs/embargo-policy.yaml EP-09-002;
  specs/case-management.yaml CM-14-011; specs/case-ledger-processing.yaml CLP-10-006;
  specs/outbox.yaml OX-14-002; docs/adr/0066-outbox-terminal-state.md;
  vultron/core/behaviors/case/AGENTS.md (ISSUE-1325); ISSUE-3033, ISSUE-2898
informed: []
stakeholder_type: [project-contributor]
---

# The Case Ledger Records Completed Acts

## Context and Problem Statement

A case message is an act: "I asked you something", "I told you something", or "you asked or told me something".
A case ledger entry is a record of such an act: "I hereby record that I told you X".
A record of an act that has not happened yet records an intention, not an act, and the ledger then claims something that may never become true.

Six places in the project currently require the opposite order for messages this node sends, committing the entry first and sending afterwards:

- SYNC-09-002 says external Vultron messages "MUST only be emitted after the associated `CaseLedgerEntry` is committed".
- SBT-04-004 implements it: "External activities MUST NOT be emitted before the associated CaseLedgerEntry is committed".
- `vultron/core/behaviors/case/AGENTS.md` § "Ledger Commit Must Precede Outbox Write" (ISSUE-1325) requires the commit before the outbox write, so that a failed commit cannot leave a queued activity with no record, which a retry would then send twice.
- EP-09-002's embargo-revision relay emits each Invite and commits each emission, and the implementation commits before it queues.
- OX-14-002 forbids deferring a commit until delivery is confirmed, and its verification requires the committed entry to be present in the canonical ledger before any delivery attempt for its activity.
- [ADR-0066](0066-outbox-terminal-state.md) states an emit-after-commit invariant: the `CaseLedgerEntry` is always committed before its fan-out activity is queued, so a dead-lettered activity can always be resolved to its entry.

The case-setup sequence already contradicts the rule.
CM-14-011 sends `Create(VulnerabilityCase)` to the reporter before the first ledger commit, and CM-14-001 forbids reordering its steps.
When the CaseProposal accept tree followed SYNC-09-002 literally, the ledger fan-out reached recipients ahead of the `Create` that told them the case existed, every recipient took the pre-genesis reject-and-replay path on the normal route, and the suite went flaky (ISSUE-3033, ISSUE-2898).
The fix followed CM-14-011 and recorded the reconciliation in one rationale field, leaving SYNC-09-002's statement unqualified.

What order should a node use when it both sends a message and records it?

## Decision Drivers

- A ledger entry is evidence that something happened, so it must not precede the thing it records.
- Replicas and auditors read the ledger as history; an entry for a send that never happened is false history.
- A retry after a partial failure must not send the same activity twice.
- The node controls its own outbox but not delivery to a peer, which may be unreachable for hours.

## Considered Options

- Commit, then send (the current rule).
- Keep commit-then-send, and narrow SYNC-09-002 to exempt the case-seeding bootstrap messages.
- Send, then commit: record a sent message once it has been delivered to the node's own outbox.

## Decision Outcome

Chosen option: "Send, then commit", because it is the only option in which every ledger entry records an act that has happened.

A send is done when the activity has been delivered to the sending node's own outbox.
At that point the node has irrevocably committed to sending it, and delivery to the peer is the outbox's job, with its own retries.
The ledger entry for a sent message is therefore committed after the outbox write.

A received message is recorded after intake, as it is today: the receive-side order of intake, guards, commit and effects (CLP-10-006) already records an act that has happened, and does not change.
An effect that sends a message as a consequence of a received one is a send like any other, recorded after its own outbox write.

`Announce(CaseLedgerEntry)` is the one message that follows a commit, and it does not contradict the rule.
It is not an act the ledger records; it is the record itself, replicated to the participants.

### Consequences

- Good, because every ledger entry records a completed act, so a replica never holds a record of a message that was never sent.
- Good, because the case-setup order of CM-14-011 becomes an instance of the rule rather than an exception to it, and no message needs an exemption list.
- Good, because the pre-genesis race behind ISSUE-3033 cannot recur: the case reaches its recipients before any entry that refers to it.
- Bad, because the duplicate-send protection ISSUE-1325 relied on goes away and has to be replaced: on a retry after a send whose commit failed, the node must find the activity already in its outbox, by activity id, and must not send it again.
- Bad, because every emitting tree that commits first has to be reordered, and SYNC-09-002, SBT-04-004 and EP-09-002's ordering must be rewritten.
- Neutral, because OX-14-002's statement still holds: the commit waits for the outbox write, not for delivery to the peer.
  Its verification must be rewritten, because the outbox write, and so the first delivery attempt, can now come before the commit.
- Neutral, because ADR-0066's emit-after-commit invariant must be rewritten for sent messages.
  `Announce(CaseLedgerEntry)` fan-out still follows its commit, so dead-letter correlation for ledger replication is unchanged, but the activity a ledger entry records is queued before that entry exists.
- Neutral, because a crash between the outbox write and the commit leaves a sent activity with no ledger entry until the retry records it, which is the honest state: the act happened and its record is pending.

## Validation

Epic #4158 carries the work.
Once this ADR is accepted, SYNC-09-002, SBT-04-004, EP-09-002, OX-14-002's verification and ADR-0066's emit-after-commit invariant state the order this ADR sets, and a test of each emitting tree asserts that the outbox write precedes the commit that records it and that a retry after a failed commit sends nothing twice.

## Pros and Cons of the Options

### Commit, then send

- Good, because a failed commit stops the send, so no activity leaves without a record.
- Bad, because the entry records an intention, and if the send then fails the ledger holds a record of something that never happened.
- Bad, because it contradicts CM-14-011, and following it literally caused the ISSUE-3033 and ISSUE-2898 flakes.

### Keep commit-then-send and exempt bootstrap messages

- Good, because it is the smallest change to the specs.
- Bad, because every message outside the exemption is still recorded before it is sent, so the ledger still records intentions.
- Bad, because the exemption is a list someone must remember to extend for each new seeding message.

### Send, then commit

- Good, because the ledger records only completed acts.
- Good, because sent and received messages follow one principle.
- Bad, because duplicate-send protection has to move from the ledger to an outbox-id check.

## More Information

Decided with the maintainer in the 2026-10-02 `learn` session, which considered narrowing SYNC-09-002 and rejected it in favour of this principle.
Until this ADR is accepted, new code follows the current specs, which still require the commit before the send; this ordering is under review.
