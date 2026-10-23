---
title: "CreateParticipantStatusNode persists VFD state without transition validation"
type: learning
timestamp: "2026-07-30T00:00:00Z"
source: ISSUE-1825-b
signal: concern
---

`CreateParticipantStatusNode.update` (`vultron/core/behaviors/case/nodes/
participant/status.py`) constructs `VfdDimension(state=<target>)` directly and
persists it, never calling `VfdDimension.transition()` or
`is_valid_vfd_transition`. So the validity of a VFD/RM/PXA state change is
enforced **only** by whatever guard node precedes the transition node in the
tree — nothing at the persistence boundary rejects an illegal jump (e.g.
`vfd → VFD`).

This surfaced in #1825: the first-draft `CheckCSFixNotYetDeployed` guard was too
weak and would have allowed an invalid `vfd/Vfd → VFD` snapshot. The guard was
strengthened, but the underlying fragility remains for every tree that writes
status via this node.

**Why:** state-machine validity lives in the dimension objects
(`.transition()`), but the write path bypasses it — a fail-open design that
relies on upstream BT guards being correct.

**How to apply:** consider having `CreateParticipantStatusNode` (or a shared
helper) validate the requested state against the participant's current state
via the dimension `transition()` machinery, returning FAILURE on an invalid
transition. That would make invalid jumps fail-closed regardless of guard
coverage. Worth a GitHub Concern issue if not already tracked.
See [[20260730-1825-checkcsfixnotyetdeployed-guard-strength]].

**Promoted**: 2026-07-31 — captured in `notes/bt-pitfalls.md` (CreateParticipantStatusNode bypass section). GitHub concern: #1896.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1900>0>0>0>0>.
