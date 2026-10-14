---
title: Peer Broadcast Failure Semantics
status: active
kind: guidance
description: >
  Peer fan-out failure must surface as FAILURE (BT-14-001), with one exception:
  a best-effort notification after a committed mutation inside a Selector whose
  fallback always succeeds.
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-pitfalls.md
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
