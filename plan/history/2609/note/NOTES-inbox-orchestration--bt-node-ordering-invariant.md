---
source: NOTES-inbox-orchestration--bt-node-ordering-invariant
timestamp: '2026-09-17T17:25:22.718983+00:00'
title: BT Node Ordering Invariant
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b,e) matches inbox_tree.py; normative in IO spec
**Superseded by:** vultron/core/behaviors/.../inbox_tree.py; specs/inbox-orchestration.yaml

---

## BT Node Ordering Invariant

The BT implementation enforces a fixed pipeline via Sequence nodes:

```text
Sequence
  ├─ ParsePayloadNode       (ingress_adapter → as_Activity)
  ├─ RehydrateActivityNode  (rehydrate nested objects)
  ├─ ExtractSemanticsNode   (as_Activity → MessageSemantics)
  ├─ DeferCheckNode         (case context readiness check)
  ├─ DispatchNode           (dispatch_adapter → use case)
  └─ BuildOutcomeNode       (assemble InboxOutcome)
```

The Sequence guarantees that callers can never invoke steps out of order.
BT node names are descriptive and observable — the tree structure is the
workflow documentation.

---
