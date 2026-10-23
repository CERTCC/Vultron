---
source: NOTES-inbox-pipeline--context
timestamp: '2026-09-17T17:25:23.569777+00:00'
title: Context
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) pre-build risk framing; safety net built
**Superseded by:** vultron/adapters/driving/fastapi/inbox_pipeline.py

---

## Context

`vultron/adapters/driving/fastapi/inbox_handler.py` implements the full inbox
processing pipeline:

```text
inbox queue (activity ID string)
  → rehydrate(id, dl)              # fetch + reconstruct full AS2 object
  → extract_event(activity)        # AS2 → domain AnyReceivedEvent
  → _dispatch_or_defer_inbox_item  # check case context, maybe defer
  → dispatcher.dispatch(event, dl) # route to use-case
  → use_case.execute()
```

All existing unit tests mock either `_DISPATCHER` or `prepare_for_dispatch`.
No unit test exercises the real chain end-to-end. That flow is covered only
by slow demo integration tests in `test/demo/`.

**The risk**: if a new semantic type is added but its `SEMANTIC_REGISTRY`
use-case registration is forgotten, all mock-based unit tests pass and the
failure only surfaces in production or the slow integration suite.

---
