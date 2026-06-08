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

## Scope Boundary

This guidance addresses fail-fast semantics and consistency of existing
broadcast paths.

Out of scope for this phase:

- Protocol-level delivery guarantees (`at-least-once`, `exactly-once`)
- Queue durability redesign
- Full dead-letter pipeline design

Those can be layered later without reintroducing silent success behavior.
