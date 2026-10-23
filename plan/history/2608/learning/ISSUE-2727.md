---
title: get_failure_reason DFS masks actual AnnounceLogEntryReceivedBT failure cause
type: learning
timestamp: 2026-08-28T00:00:00Z
source: ISSUE-2727
signal: concern
---

`BTBridge.get_failure_reason` does a DFS left-to-right traversal and returns the
FIRST leaf node with `Status.FAILURE`. In `AnnounceLogEntryReceivedBT` the first
child is `CaseActorSubtree` whose first node is `CheckIsOwnCaseActorNode`. That
node ALWAYS fails for non-CaseActor actors (it's a routing condition, not an error).

Consequence: any failure in `AnnounceLogEntryReceivedBT` — even one deep in
`ParticipantGate` such as `CheckHashOrRejectOnMismatch` — is logged as
"BT execution completed: Status.FAILURE … - CheckIsOwnCaseActorNode", pointing
investigators to normal routing logic rather than the real failure.

In ISSUE-2727 this delayed diagnosis by several investigation rounds; the actual
cause (genesis hash mismatch from divergent `published` timestamps) was buried
three levels deeper in `ProcessAndStore → CheckHashOrRejectOnMismatch →
SendRejectLogEntryNode`.

Consider: post an additional INFO log after `get_failure_reason` that also
reports the DEEPEST failure node (not just the first), or change
`AnnounceLogEntryReceivedBT` to use a dedicated "routing expected-failure" node
class that `get_failure_reason` can skip.
