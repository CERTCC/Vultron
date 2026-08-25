---
source: CONCERN-1896
timestamp: '2026-08-07T19:01:23.985396+00:00'
title: CreateParticipantStatusNode persists VFD/RM/PXA state without transition validation
type: learning
---

## Concern

`CreateParticipantStatusNode.update()` constructed `VfdDimension(state=target)`
directly, bypassing `VfdDimension.transition()` and all validity checks. Any
weak, missing, or bypassed upstream guard could allow an illegal state jump to
be persisted. The same structural gap exists in `rm_transitions.py`.

## Resolution

Added spec requirements establishing that BT write nodes MUST validate
source→target transitions before persisting, making the write path fail-closed
regardless of upstream guard coverage.

- Same-state writes (target == current) are permitted as status confirmations.
- None targets skip validation (preserve current state).
- Illegal jumps MUST cause the node to return `Status.FAILURE` with a
  descriptive `feedback_message`.

## Specs and Notes Updated

- **BTND-10-001** (`specs/behavior-tree-node-design.yaml`): BT status-write
  nodes MUST validate VFD/RM/PXA transitions before persisting
- **SDO-02-004** (`specs/status-dimension-objects.yaml`): direct-construction
  call sites MUST validate source→target; refines SDO-02-002
- **CSB-16-001/002** (`specs/cs-behavior.yaml`): VFD and PXA write boundaries
  MUST reject illegal jumps and backward moves
- **`notes/status-dimension-objects.md`**: "Write-Side Validation at BT Nodes"
  section with canonical code pattern

## Implementation Issues

- #2081: validate VFD/RM/PXA transitions in `CreateParticipantStatusNode` (Schedule=Focus)
- #2082: validate RM transitions in `rm_transitions.py` (Schedule=Focus, blocked-by #2081)

Docs PR: <https://github.com/CERTCC/Vultron/pull/2080>
