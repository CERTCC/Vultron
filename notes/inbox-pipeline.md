---
title: Inbox Pipeline — InboxPipeline Design Notes
status: active
description: >
  Design decisions, implementation guidance, and test patterns for the
  `InboxPipeline` class and `build_test_pipeline()` factory that surface
  the `inbox_handler → dispatcher` seam as a testable unit.
related_specs:
  - specs/inbox-pipeline.yaml
related_notes:
  - notes/architecture-ports.md
  - notes/architecture-hexagonal.md
  - notes/architecture-adapters.md
relevant_packages:
  - vultron/adapters/driving/fastapi
  - vultron/core/ports
  - test/adapters/driving/fastapi
---

# Inbox Pipeline — InboxPipeline Design Notes

## `UnroutableActivityError` Must Be Caught Inside `_handle`, Not Above It

(ISSUE-1377, 2026-07-14)

When a gate/guard helper is called *before* the `try/except` that wraps
use-case execution in `DispatcherBase._handle`, any exception it raises
escapes `_handle` entirely. The inbox adapter's `_process_inbox_item`
treats every exception other than `VultronProtocolViolationError` as transient
and re-queues the item — creating an infinite retry loop for any unroutable
event. A `VultronProtocolViolationError` is permanent and is not re-queued
(#2865).

```python
# ❌ WRONG — _enforce_join_backfill_gate is called BEFORE the try/except
def _handle(self, event, dl):
    self._enforce_join_backfill_gate(event, dl)   # raises UnroutableActivityError
    try:
        ...                                        # never reached for unroutable events
    except SomeOtherError:
        ...

# ✅ CORRECT — gate call is wrapped independently inside _handle
def _handle(self, event, dl):
    try:
        self._enforce_join_backfill_gate(event, dl)
    except UnroutableActivityError:
        logger.error("Unroutable event %s — dropping", event)
        return                                     # _process_inbox_item sees clean return
    try:
        ...
```

**General rule**: When converting a silent-failure (return `None` / return
`False`) into a `raise`, trace the full call stack to every exception handler
above the raise site. If any handler has re-queue / retry semantics, the new
exception MUST be caught below that handler — at the dispatch level or in a
dedicated gate wrapper. Letting it propagate restores the silent-failure
behavior as an infinite retry, which is worse.

---

## Layer and Import Rules

- `InboxPipeline` is an **adapter-layer** class; it MAY import from
  `inbox_handler.py` helpers and core ports.
- `InboxPipeline` MUST NOT be imported by any core-layer module
  (`vultron/core/`).
- `build_test_pipeline()` MAY import `make_dispatcher()` from
  `inbox_handler.py` since both are in the same adapter package.
- The pytest fixture belongs in
  `test/adapters/driving/fastapi/conftest.py` — not in a top-level
  conftest — to keep its scope narrow.

---
