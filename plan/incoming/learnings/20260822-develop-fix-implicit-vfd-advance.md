---
title: "TransitionCStoFixReady now advances through Vfd if actor is at vfd"
type: learning
timestamp: "2026-08-22T00:00:00Z"
source: ISSUE-2478
signal: design-question
---

Enforcing CSB-16-001 strict adjacency in `CreateParticipantStatusNode` caused three regressions in `test_develop_fix_tree.py`: `TransitionCStoFixReady` was calling `CreateParticipantStatusNode(vfd_state=CS_vfd.VFd)` from an actor at `vfd` (the default starting state), which jumps two steps and violates strict adjacency.

**Decision made**: `TransitionCStoFixReady.update()` now checks whether the actor is still at `vfd` and, if so, calls `CreateParticipantStatusNode(vfd_state=CS_vfd.Vfd)` first (implicit V event), then the `VFd` write. This advances through the required intermediate state automatically.

**Rationale**: A vendor who reports a fix ready for a new case has implicitly been vendor-aware since they engaged. Requiring callers of `TransitionCStoFixReady` to pre-advance to `Vfd` would be a leaky abstraction. The node handles the protocol detail internally.

**Side effect**: When a vendor processes a new case through `DevelopFixBT`, two `ParticipantStatus` records are now written (one for `Vfd`, one for `VFd`) instead of one. The narrative log emits two CS INFO lines. The `test_fix_ready_logged_in_narrative_form` test was updated accordingly.

**Spec note**: The DevelopFix BT spec (`specs/behavior-tree-integration.yaml`) does not document this intermediate-state advancement. A spec update may be warranted.
