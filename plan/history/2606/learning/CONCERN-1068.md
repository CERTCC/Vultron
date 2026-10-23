---
source: CONCERN-1068
timestamp: '2026-06-22T14:27:46.447081+00:00'
title: Receive-side BT commit-before-effects ordering
type: learning
---

## Summary

Across receive-side behavior trees, protocol-significant actions (state
transitions, outbox enqueues, participant updates, etc.) are taken before
the triggering received message is committed to the canonical case ledger.
This inverts cause-before-effect ordering: the case ledger may record effects
without the cause that produced them.

## Category

- Technical debt
- Correctness / causal ordering

## Severity

High

## Evidence

The pattern is present in receive-side BTs throughout `vultron/core/behaviors/`
— `CommitCaseLedgerEntryNode` (if present at all) appears after
state-transition or outbox nodes rather than as the first node in the
sequence. This pattern appears to have emerged early in the receive-side BT
implementation and has been consistently repeated.

Confirmed violations at time of audit (main as of commit df04902f):

- `received/embargo.py`: `InviteToEmbargoOnCaseReceivedUseCase`,
  `AcceptInviteToEmbargoOnCaseReceivedUseCase` — two `execute_with_setup`
  calls; effect BT runs first, commit BT second
- `received/report.py`: `ValidateReportReceivedUseCase`,
  `AckReportReceivedUseCase` — same two-call pattern
- `received/status.py`: `AddParticipantStatusToParticipantReceivedUseCase`
  — same two-call pattern
- `behaviors/case/accept_invite_tree.py`: commit is last child, after
  `EmitAnnounceCaseToInviteeNode` and `BackfillCanonicalLedgerToInviteeNode`
- `behaviors/case/create_tree.py`: commit is last child, after
  `UpdateActorOutbox`
- `behaviors/embargo/announce_teardown_tree.py`: commit is last child in
  each sub-tree, after state-transition nodes
- `behaviors/report/prioritize_tree.py`: commit is 3rd child, after
  `TransitionParticipantRMtoAccepted`

## Impact if Ignored

Case ledgers will not accurately reflect the causal order of events.
Participants replicating the ledger via `Announce(CaseLedgerEntry)` may
observe effects without the causes that produced them. Forensic and audit
use of the canonical case ledger becomes unreliable.

## Resolution

Correct ordering: (1) precondition guards (read-only), (2) commit the
triggering activity, (3) all protocol effects. The commit records that the
activity was received — this is independent of whether subsequent effects
succeed.

**Resolved**: 2026-06-22 — implementation tracked in #1072 and #1073
(both blocked by #1052).
Docs PR: [#1070](https://github.com/CERTCC/Vultron/pull/1070).
Spec: `specs/case-ledger-processing.yaml` CLP-10-006.
