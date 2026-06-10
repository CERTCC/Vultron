---
source: CONCERN-651
timestamp: '2026-06-04T13:21:24.899314+00:00'
title: report/nodes.py high-churn alongside case BT nodes
type: learning
---

## Summary

`vultron/core/behaviors/report/nodes.py` has accumulated 31 commits in the
last 90 days, making it one of the top high-churn source files. Like its
sibling `case/nodes.py`, it encodes Behavior Tree semantics for the
report-management protocol and grows in tandem with case-node changes.

## Category

- [ ] Top risk
- [ ] Technical debt
- [ ] Security
- [ ] Performance / scaling
- [x] Fragile / high-churn area
- [ ] Other

## Severity

low

## Evidence

- `vultron/core/behaviors/report/nodes.py` (31 churn hits / 90 days,
  1063 lines, 15 BT node classes)
- Scan output: high-churn source-file ranking

## Impact if Ignored

Concurrent changes to report and case BT nodes create merge-conflict risk.
Protocol-significant BT logic may drift from spec if changes are not covered
by targeted unit tests.

## Suggested Action

Keep unit tests per BT node. Extract shared helpers before adding new nodes.
Coordinate changes to `report/nodes.py` and `case/nodes.py` in the same PR
when they interact.

**Resolved**: 2026-06-04 — implementation tracked in #738. No docs PR
required: the relevant spec (`specs/behavior-tree-node-design.yaml`
BTND-07-001, BTND-07-002) and the AGENTS.md pitfall entry ("Flat
`nodes.py` with 10+ BT Classes Is a Code Smell") already exist from the
sibling concern #514 / PR #737. Concern #651 falls directly under those
existing requirements; the impl issue applies the same refactor pattern
as #736 to the report-management BT nodes.
