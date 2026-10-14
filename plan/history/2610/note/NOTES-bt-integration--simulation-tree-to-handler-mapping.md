---
source: NOTES-bt-integration--simulation-tree-to-handler-mapping
timestamp: '2026-10-12T19:35:41.493012+00:00'
title: Simulation tree to handler mapping
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered migration table; every listed handler is implemented as a py_trees use-case tree
**Superseded by:** vultron/core/behaviors/report/

---

**Simulation tree to handler mapping**:

| Handler             | Simulation Reference                              | Status                |
|---------------------|---------------------------------------------------|-----------------------|
| `validate_report`   | `_behaviors/validate_report.py:RMValidateBt`      | ✅ DONE               |
| `engage_case`       | `_behaviors/prioritize_report.py:RMPrioritizeBt`  | ✅ DONE               |
| `defer_case`        | `_behaviors/prioritize_report.py:RMPrioritizeBt`  | ✅ DONE               |
| `create_case`       | `case_state/conditions.py`, `transitions.py`      | ✅ DONE               |
| `invalidate_report` | `_behaviors/validate_report.py:_InvalidateReport` | ⚠️ Optional refactor  |
| `close_report`      | `_behaviors/close_report.py:RMCloseBt`            | ⚠️ Optional refactor  |
