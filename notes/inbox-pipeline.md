---
title: Inbox Pipeline — InboxPipeline Design Notes
status: active
kind: guidance
description: >
  Rules for the dispatcher's exception boundary and the adapter-layer
  `InboxPipeline` / `build_test_pipeline()` test seam: where unroutable errors
  are caught, how re-queues are bounded, and layer/import rules.
related_specs:
  - specs/inbox-pipeline.yaml
related_notes:
  - notes/architecture-hexagonal.md
  - notes/architecture-adapters.md
  - notes/inbox-orchestration.md
relevant_packages:
  - vultron/adapters/driving/fastapi
  - vultron/core/ports
  - test/adapters/driving/fastapi
---

# Inbox Pipeline — InboxPipeline Design Notes

The production inbox runs the core BT (`notes/inbox-orchestration.md`). This note
covers the dispatcher's exception boundary and the adapter-layer `InboxPipeline` test
seam.

## `UnroutableActivityError` Must Be Caught Inside `_handle`, Not Above It

A gate helper called before the `try/except` in `DispatcherBase._handle`
(`vultron/core/dispatcher.py`) escapes `_handle`. The inbox queue replay in
`run_inbox_pipeline` retries every exception except `VultronProtocolViolationError`,
so an escaping `UnroutableActivityError` is retried as if transient, to the retry
budget, and then dead-lettered (IE-06-004).
Wrap the gate call (`_enforce_join_backfill_gate`) in its own `try` inside `_handle`.

**General rule**: when a silent failure (return `None`/`False`) becomes a `raise`, trace
every handler above the raise site. If one has retry or re-queue semantics, catch the
new exception below it; letting it propagate turns the silent failure into an infinite
retry (ISSUE-1377).

---

## Re-queues Are Bounded Per Activity, Not Forbidden

`InboxPipeline.process()` re-queues an item that raises anything other than
`VultronProtocolViolationError` at most `MAX_REQUEUE_ATTEMPTS` times per activity ID,
then logs at ERROR and drops it; a protocol violation is dropped at once.

- **A budget, not a drop.** Some validation errors are state-dependent (genesis
  backfill not started yet) and clear on a later cycle (#2766).
- **Clear the count in a `finally` on every exit that does not re-queue**, not after
  `dispatch()`: post-dispatch work (the pending-case replay) can still raise, and
  clearing at dispatch resets the budget every cycle. A deferral also clears it.
- **Per instance, not persisted.** This test seam keeps its own count; production runs
  `run_inbox_pipeline`, whose queue replay persists its count in the `RetryStore` the
  outbox uses and dead-letters an exhausted item (IE-06-004).

---

## Layer and Import Rules

- `InboxPipeline` is an adapter-layer class; it MAY import `inbox_handler.py` helpers
  (including `make_dispatcher()`) and core ports, and MUST NOT be imported by
  `vultron/core/`.
- Its pytest fixture lives in `test/adapters/driving/fastapi/conftest.py`, not a
  top-level conftest, to keep its scope narrow.
