---
source: NOTES-embargo-default-semantics--implementation-initializedefaultembargonode
timestamp: '2026-10-12T19:33:13.690177+00:00'
title: 'Implementation: InitializeDefaultEmbargoNode'
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered; the one live rule (PROPOSED never persisted) is folded into the published-default section
**Superseded by:** vultron/core/behaviors/case/embargo_tree.py; EP-04-002; notes/embargo-default-semantics.md

---

## Implementation: `InitializeDefaultEmbargoNode`

`InitializeDefaultEmbargoNode` (in `vultron/core/behaviors/case/embargo_tree.py`;
the leaf nodes it composes live in
`vultron/core/behaviors/case/nodes/embargo_resolution.py` and `embargo.py`)
implements the default path by delegating to `EmbargoLifecycle.propose_embargo()`
followed by an internal accept, landing the case at `EM.ACTIVE` atomically. The
intermediate `EM.PROPOSED` state is never persisted or externally observable
(EP-04-002).

The case owner is seeded as a signatory in the same BT subtree immediately
after the embargo is activated (see "Case Owner Initial Embargo Consent" below).

---
