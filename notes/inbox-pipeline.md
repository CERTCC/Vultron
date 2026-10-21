---
title: Inbox Pipeline — InboxPipeline Design Notes
status: active
kind: guidance
description: >
  Rules for the dispatcher's exception boundary and the adapter-layer
  `InboxPipeline` / `build_test_pipeline()` test seam: where unroutable errors
  are caught, how re-queues are bounded, why a queue replay attempt commits
  as one transaction, and layer/import rules.
related_specs:
  - specs/inbox-pipeline.yaml
  - specs/inbox-endpoint.yaml
  - specs/datalayer.yaml
  - specs/protocol-asks.yaml
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

## A Queue Replay Attempt Commits Whole, or the Item Is Lost

Run each `drain_inbox_queue` attempt inside one `actor_dl.transaction()`: the
`inbox_pop`, the rebuild's delete of the `DeferredInboxActivity`, `process_payload`
and the settlement (`hold_again`, the attempt count, `inbox_append`, the dead letter
and the held fault) (IE-06-005).

- **Why.** The held record is the only copy the replay can rebuild the activity
  from (DL-06-006). Committed one by one, a stop after the pop or the delete leaves
  nothing queued or nothing held, and no sender is answered (ASK-07-010).
- **Nesting is the point.** The act's `ActTransaction` becomes a savepoint inside the
  attempt's block, so a failed act still keeps nothing (ADR-0151) while the
  settlement that follows it commits with the pop.
- **Surviving is not recovering.** A surviving item waits for the next delivery to
  that actor unless the startup drain replays it (IE-06-006).

---

## Layer and Import Rules

- `InboxPipeline` is an adapter-layer class; it MAY import `inbox_handler.py` helpers
  (including `make_dispatcher()`) and core ports, and MUST NOT be imported by
  `vultron/core/`.
- Its pytest fixture lives in `test/adapters/driving/fastapi/conftest.py`, not a
  top-level conftest, to keep its scope narrow.
