---
title: "Introduce CasePersistence and CaseOutboxPersistence narrow Protocols (RFC-403)"
type: implementation
date: 2026-04-30
source: TASK-RFC-403
---

# Introduced CasePersistence and CaseOutboxPersistence narrow Protocols (RFC-403)

## Summary

Replaced all direct `DataLayer` imports in core use cases and BT nodes with two narrow Protocol classes:

- `CasePersistence` (7 methods: `create`, `read`, `get`, `save`, `by_type`, `find_case_by_report_id`, `find_actor_by_short_id`)
- `CaseOutboxPersistence(CasePersistence)` (adds `record_outbox_item`, `outbox_append`)

## Files Created

- `vultron/core/ports/case_persistence.py`

## Files Modified

- `vultron/core/behaviors/helpers.py` — BT base classes use `CasePersistence`; `cast()` for `update()` and `record_outbox_item()`
- `vultron/core/behaviors/bridge.py` — `BTBridge.__init__` param narrowed to `CasePersistence`
- `vultron/core/behaviors/case/nodes.py` — narrowed; cast for outbox/commit trigger calls
- `vultron/core/behaviors/report/nodes.py` — cast for outbox calls
- `vultron/core/behaviors/case/suggest_actor_tree.py` — cast for outbox calls
- `vultron/core/use_cases/_helpers.py`, `triggers/_helpers.py`, and all trigger/received use-case files

## Outcome

All four linters (Black, flake8, mypy, pyright) pass cleanly. All 1962 tests pass.
