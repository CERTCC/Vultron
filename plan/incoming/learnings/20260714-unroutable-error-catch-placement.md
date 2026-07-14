---
title: Catch UnroutableActivityError in _handle, not at call site
type: learning
timestamp: '2026-07-14T00:00:00+00:00'
source: ISSUE-1377
---

When raising a domain exception from a gate/guard helper called early in a dispatch
method (before the main `try/except` block), the exception must be caught and handled
by the dispatch method itself — not left to propagate to the caller.

In `DispatcherBase._handle`, `_enforce_join_backfill_gate` is called at line 101
*before* the `try` block that wraps use-case execution at line 107. When
`_extract_case_id` was changed to raise `UnroutableActivityError` instead of
returning `None`, the exception escaped `_handle` entirely. The inbox adapter's
`_process_inbox_item` catches all `Exception` at line 326 and re-queues the item —
creating an infinite retry loop for any unroutable event.

**Fix**: wrap the gate call in its own `try/except UnroutableActivityError` inside
`_handle`, log at ERROR, and return (drop the event). The infinite loop cannot occur
because `dispatch()` completes normally, `_process_inbox_item` sees a clean return, and
the item is not re-queued.

**General rule**: When converting a silent-failure (return None / return False) into a
raise, trace the full call stack to every exception handler above the raise site. If any
handler has re-queue / retry semantics, the new exception must be caught below that
handler — either at the dispatch level or in a dedicated gate wrapper.
