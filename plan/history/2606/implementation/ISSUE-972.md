---
source: ISSUE-972
timestamp: '2026-06-16T14:41:40.418285+00:00'
title: Split inbox_handler.py into focused processing modules
type: implementation
---

## Issue #972 — Split inbox_handler.py into focused processing modules

Split the 666-line `vultron/adapters/driving/fastapi/inbox_handler.py`
into three focused submodules, reducing the main file to 413 lines and
eliminating code duplication with `inbox_pipeline.py`.

### New modules

- `inbox_port_factories.py` (113 lines): port factory functions
  (`_sync_port_factory`, `_trigger_activity_port_factory`,
  `_sync_and_trigger_port_factory`) and the three disjoint semantics-set
  constants
- `inbox_pending_queue.py` (239 lines): pre-bootstrap pending case queue
  helpers (`_activity_context_id`, `_queue_pending_case_activity`,
  `_expire_pending_case_activities`, `_replay_pending_case_activities`)

### Updated modules

- `inbox_handler.py`: reduced from 666 to 413 lines; re-exports all moved
  names for backward compatibility; retains dispatcher management and the
  main processing flow
- `inbox_pipeline.py`: removes local duplicate copies of
  `_activity_context_id` and `_queue_pending_case_activity`; imports from
  `inbox_pending_queue` instead

### Outcome

All 2945 unit tests and 417 fastapi/demo tests pass. Black, flake8, mypy,
and pyright are all clean. No behavioral changes — pure refactor.

PR: [#988](https://github.com/CERTCC/Vultron/pull/988)
