---
source: NOTES-embargo-lifecycle--current-fragmentation
timestamp: '2026-09-17T17:22:58.511563+00:00'
title: Current Fragmentation (the problem)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,c) #538/#516 closed; triggers/embargo.py now a package; conclusion false
**Superseded by:** vultron/core/behaviors/embargo/; notes/embargo-lifecycle.md § Current Architecture

---

## Current Fragmentation (the problem)

EM state transition logic is currently duplicated across several places:

| Module | Role | Lines | Status |
|---|---|---|---|
| `vultron/core/states/em.py` | EM state machine definition | ~150 | — |
| `vultron/core/states/participant_embargo_consent.py` | PEC machine | ~155 | — |
| `vultron/core/use_cases/triggers/embargo.py` | Trigger-side (5 use-case classes + 10 module-level helpers) | ~902 | needs migration |
| `vultron/core/use_cases/received/embargo.py` | Receive-side (7 use-case classes) | ~482 | needs migration |
| `vultron/core/behaviors/embargo/nodes/` | BT-side autonomous management | — | partially migrated (see below) |

**BT-side migration progress** (EMB-18-001, issue #2480):

- `ClearActiveEmbargoNode` — migrated (PR #2691); routes through
  `EmbargoLifecycle.terminate_active_embargo()`
- `SetEmbargoActiveNode` — migrated (PR #2691, issue #2696); routes through
  `EmbargoLifecycle.activate_embargo()` in STRICT mode; returns FAILURE
  for non-standard EM transitions (EMB-18-002)
- `AdvanceEMStateToActiveNode` — migrated; uses `EmbargoLifecycle.propose_embargo()`
- `WriteEmStateNode` — **retired** (PR #2816, issue #2712); the last BT node
  that directly assigned `EmDimension` to `case.current_status.em`. All five
  `EmbargoLifecycle` service methods now unconditionally own their own EM reads
  and writes. The `caller_owns_em_io` pattern is fully removed.

BT-side direct EM assignment is **complete**. `EmbargoLifecycle` is the single
authoritative owner for EM state writes on the BT side. Trigger-side and
received-side use cases are still pending migration — bugs fixed in the service
will not propagate to them until they are migrated.

---
