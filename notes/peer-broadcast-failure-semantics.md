---
title: Peer Broadcast Failure Semantics
status: active
related_specs:
  - specs/behavior-tree-integration.yaml
related_issues:
  - https://github.com/CERTCC/Vultron/issues/782
---

# Peer Broadcast Failure Semantics

## Problem

Some behavior-tree fan-out paths treat broadcast delivery failures as
non-fatal and still report `SUCCESS`. This creates a false-success condition:
local workflows appear complete while peers miss state updates.

In a federated CVD protocol, this is a correctness risk because participant
state can silently diverge without any explicit signal to callers.

## Required Behavior

For protocol-visible peer fan-out:

1. Broadcast preparation or enqueue failure must return `FAILURE`.
2. Parent BT control flow must be able to react to that failure.
3. A guaranteed-success fallback that masks delivery failure is not allowed.

These rules are captured in `BT-14-001`.

## Design Direction

Use a shared helper/subtree for fan-out phases:

1. Resolve sender/manager context.
2. Filter recipient set.
3. Construct broadcast activity.
4. Enqueue to outbox.

This keeps failure semantics consistent across domains (status, embargo, and
future peer-broadcast paths). This direction is captured in `BT-14-002`.

## Best-Effort Override Exception

BT-14-001 requires FAILURE on broadcast failure. There is one documented
exception: **receive-side nodes that sit inside a Selector with a
guaranteed-SUCCESS fallback AND follow a state mutation that has already
been committed**.

In this pattern, FAILURE semantics break the Selector invariant. If the
broadcast node returns FAILURE, the Selector falls through to the fallback
`AlwaysSuccess` child — making it appear the earlier guard condition was
never satisfied, even though the DataLayer state mutation has already been
written. This is confusing and hard to detect.

**When the override applies:**

- The node is positioned AFTER a state-mutation node in a `Sequence`.
- The Sequence is the non-fallback arm of a `Selector`.
- The Selector's fallback arm is `AlwaysSuccess` (or equivalent).
- The missing prerequisite (factory, recipient) is an operational gap,
  not a data error.

**Correct behavior in this case:** `SUCCESS + WARNING` — teardown must not
be blocked by notification gaps. The missing-factory case is an operational
deployment gap (receive-side use cases don't wire factories), not a data
error that should roll back state.

**Canonical examples:** `SendAnnounceEmbargoEventNode` in
`vultron/core/behaviors/embargo/nodes/teardown.py` — returns SUCCESS with
WARNING when `trigger_activity_factory` is `None` or no Case Manager is
found, rather than FAILURE. `EmitCloseCaseNode` in
`vultron/core/behaviors/status/nodes/lifecycle.py` uses the same override
(PR #1724).

**When the override does NOT apply:** when the node sits directly in a
Sequence without a fallback-SUCCESS Selector parent, FAIL-FAST per
BT-14-001 is still correct.

See `plan/incoming/learnings/20260727-bt-announce-factory-absent-semantics.md`
for the full design rationale.

## Scope Boundary

This guidance addresses fail-fast semantics and consistency of existing
broadcast paths.

Out of scope for this phase:

- Protocol-level delivery guarantees (`at-least-once`, `exactly-once`)
- Queue durability redesign
- Full dead-letter pipeline design

Those can be layered later without reintroducing silent success behavior.
