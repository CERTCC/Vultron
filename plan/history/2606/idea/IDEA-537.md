---
source: IDEA-537
timestamp: '2026-06-04T15:06:53.199636+00:00'
title: InboxPipeline testable inbox seam
type: idea
---

## RFC: Add `InboxPipeline` to surface the `inbox_handler → dispatcher` seam as a testable unit

### Problem

`vultron/adapters/driving/fastapi/inbox_handler.py` (372 lines) implements the
full inbox processing pipeline:

```text
inbox queue (activity ID string)
  → rehydrate(id, dl)              # fetch + reconstruct full AS2 object
  → extract_event(activity)        # AS2 → domain VultronEvent
  → _dispatch_or_defer_inbox_item  # check case context, maybe defer
  → dispatcher.dispatch(event, dl) # route to use-case
  → use_case.execute()
```

All 7 existing unit tests mock either `_DISPATCHER` or `prepare_for_dispatch`.
No unit test exercises the real chain end-to-end. That flow is only covered by
slow demo integration tests (`test/demo/`).

**The risk this creates**: if a new semantic type is added but its
`use_case_map()` registration is forgotten, all existing unit tests pass and
the failure only surfaces in production (or the slow integration suite).

**Untested behaviors in the real pipeline:**

- The correct use-case fires for each semantic type
- Activity with unknown case context → deferred, not dispatched
- `ANNOUNCE_VULNERABILITY_CASE` → deferred activities replayed
- Error handling: use-case raises → activity re-queued, error count tracked

The `ActivityDispatcher` and `DataLayer` ports already exist and are the right
injection points — they are just not used this way today because the dispatcher
is a module-level global (`_DISPATCHER`) initialized at startup.

### Proposed Interface

Add a small `InboxPipeline` class and `build_test_pipeline()` factory that
honour the existing ports and make the real pipeline testable without mocks.

The existing `inbox_handler.py` module-level global `_DISPATCHER` is unchanged
— `InboxPipeline` is a parallel path for tests and future adapter variants,
not a rewrite.

### Design decisions (resolved during ingestion)

- Pipeline path: full `_process_inbox_item` (deferral + error requeue)
- Location: `vultron/adapters/driving/fastapi/inbox_pipeline.py`
- Return type: `VultronEvent | None` (None on deferral or error)
- Factory + pytest fixture in conftest.py
- No ADR (purely additive, no evaluated alternatives)
- Spec prefix: IBP in `specs/inbox-pipeline.yaml`
- Test scope: one routing-safety-net test per semantic domain (~7 tests)

**Processed**: 2026-06-04 — design decisions captured in
`specs/inbox-pipeline.yaml` (IBP-01 through IBP-04) and `notes/inbox-pipeline.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/768>. Implementation tracked in #769.
