---
title: Peer Broadcast Failure Semantics
status: active
kind: guidance
description: >
  Peer fan-out failure must surface as FAILURE (BT-14-001), with two exceptions:
  a best-effort notification after a committed mutation inside a Selector whose
  fallback always succeeds, and a fan-out's held-back catch-up of a paused peer
  (BT-14-003).
related_specs:
  - specs/behavior-tree-integration.yaml
  - specs/sync-ledger-replication.yaml
  - specs/case-ledger-processing.yaml
related_notes:
  - notes/bt-pitfalls.md
  - notes/sync-ledger-replication.md
---

# Peer Broadcast Failure Semantics

## The Rule (BT-14-001)

For protocol-visible peer fan-out, a failure to prepare or enqueue the broadcast
returns `FAILURE`, so the parent tree can react. A fallback that guarantees
`SUCCESS` and masks the failure is not allowed. **Why:** a false success leaves
peers silently diverged while the local workflow looks complete.

Fan-out phases (resolve sender/manager, filter recipients, build the activity,
enqueue) should share one helper or subtree, so every domain fails the same way
(BT-14-002).

## Best-Effort Exception

Return `SUCCESS` with a `WARNING` instead when **all** of these hold:

- the node runs after a state mutation that is already committed, in a
  `Sequence`;
- that `Sequence` is the non-fallback arm of a `Selector` whose fallback is
  `AlwaysSuccess` (or equivalent);
- the missing prerequisite (activity factory, Case Manager recipient) is an
  operational gap, not a data error.

**Why:** a FAILURE there makes the Selector fall through to its fallback, which
reads as "the guard never matched" although the mutation is already written.
Teardown must not be blocked by a notification gap.

Examples: `SendAnnounceEmbargoEventNode`
(`vultron/core/behaviors/embargo/nodes/teardown.py`) and `EmitCloseCaseNode`
(`vultron/core/behaviors/status/nodes/lifecycle.py`). Both still fail on hard data
errors. A node directly in a `Sequence` with no such Selector parent fails fast.

## Held-Back Catch-Up Exception (BT-14-003)

A fan-out whose catch-up backfill of a let-back-in, paused peer is held back at an
older entry (SYNC-03-009) skips only that peer and returns `SUCCESS`. **Why:** the
peer keeps its pause, so the same hold-back comes back on every later commit, and
failing would refuse each of those acts whole (CLP-07-015). Before a new send path
returns `FAILURE` on a hold-back inside an act, check whether a kept pause makes the
hold-back recur on every later act; if it does, skip the stalled peer instead.
`SendLogEntryToEachNode` (`vultron/core/behaviors/sync/nodes/fanout.py`).
