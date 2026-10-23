---
source: NOTES-bt-integration--performance-baseline
timestamp: '2026-10-12T19:35:42.704673+00:00'
title: Performance Baseline
type: note
---

**Archived:** 2026-10-12
**Reason:** historical Phase BT-1 measurement of a delivered tree; no open work depends on it
**Superseded by:** git history

---

## Performance Baseline

Phase BT-1 measurements (100 runs of `validate_report` BT):

- P50 = 0.44ms, P95 = 0.69ms, P99 = 0.84ms

This is well within the 100ms target. If more complex trees degrade
performance, consider caching BT structure (instantiate once, reuse with
fresh blackboard) and batching DataLayer operations. Measure before
optimizing.
