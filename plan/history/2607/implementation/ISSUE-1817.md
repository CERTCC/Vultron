---
source: ISSUE-1817
timestamp: '2026-07-30T19:06:11.775592+00:00'
title: create_assign_cve_id_tree — full CVE ID assignment BT
type: implementation
---

## Issue #1817 — feat(report): create_assign_cve_id_tree — full CVE ID assignment BT

Implemented full 21-node CVE ID assignment behavior tree grounded in CNA Operational Rules v4.1.0 (5 composites + 14 factory call-out leaves + 2 ProtocolInternal leaves).

**New files:**

- `vultron/core/behaviors/report/assign_cve_id_tree.py` — `create_assign_cve_id_tree()` with `_IsIDAssignmentAuthorityNode` and `_IsOrWillBePubliclyDisclosedNode` ProtocolInternal nodes
- `vultron/core/behaviors/call_out/bundles/assign_cve_id.py` — `AssignCveIdCallOutBundle` (14 fields), `ASSIGN_CVE_ID_DETERMINISTIC`
- `vultron/demo/fuzzer/bundles/assign_cve_id.py` — `ASSIGN_CVE_ID_STOCHASTIC` (14 stochastic factories)
- `test/core/behaviors/report/test_assign_cve_id_tree.py` — 29 tests

**Modified files:**

- `vultron/demo/fuzzer/report_management/assign_vul_id.py` — 10 new EvaluatorCallOutPoint nodes
- Core and demo bundles `__init__.py` — re-export new names
- `test_bundles.py`, `test_stochastic_bundle_scenario.py`, `test_nodes.py` — coverage for new bundle

PR: <https://github.com/CERTCC/Vultron/pull/1835>
