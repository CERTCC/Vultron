---
source: NOTES-bt-fuzzer-nodes-report-management--a-nonew-flag-implies-an-upstream-sentinel-seam
timestamp: '2026-10-12T19:38:59.428058+00:00'
title: A NoNew* Flag Implies an Upstream Sentinel Seam
type: note
---

**Archived:** 2026-10-12
**Reason:** obsolete: Sentinel is no longer a call-out shape, so recording a flag writer as a Sentinel call-out point is no longer the rule
**Superseded by:** ADR-0097; BT-18-013; reclassification tracked in #3424

---

## A `NoNew*` Flag Implies an Upstream Sentinel Seam

A BT condition node named `NoNew*` does not compute anything — it *reads a flag*
that something else had to write. Whenever you meet one, trace the flag to its
writer and record that writer as a **Sentinel** call-out point in the catalog. The
node is the consumer; the seam is upstream of it, outside the tree.

The three worked instances are
[`bt-fuzzer-rm-validation.md`](bt-fuzzer-rm-validation.md) § "`NoNewValidationInfo`",
[`bt-fuzzer-rm-prioritization.md`](bt-fuzzer-rm-prioritization.md), and
[`bt-fuzzer-rm-fix.md`](bt-fuzzer-rm-fix.md): in each, the Sentinel registers with
an external event source and writes a change-detection flag to the BT blackboard
or local DataLayer, which the `NoNew*` node then reads each tick. Shape assignment
follows ADR-0024's seam-structure decision tree, not the flag's automation
potential — see [`call-out-configuration.md`](call-out-configuration.md).

Leaving the Sentinel unrecorded makes the node look self-contained and hides a
real integration point, which is how the stub gaps below arise.
