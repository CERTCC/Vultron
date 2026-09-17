---
source: NOTES-inbox-pipeline--class-design
timestamp: '2026-09-17T17:25:24.144013+00:00'
title: Class Design
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) skeleton duplicating shipped class
**Superseded by:** vultron/adapters/driving/fastapi/inbox_pipeline.py

---

## Class Design

```python
# vultron/adapters/driving/fastapi/inbox_pipeline.py

class InboxPipeline:
    """Single-item inbox processing seam for tests and adapter variants.

    Wraps the full _process_inbox_item chain (rehydrate → extract → defer
    or dispatch → requeue on error) with injected ports so callers do not
    need to monkeypatch module-level globals.
    """

    def __init__(
        self,
        dispatcher: ActivityDispatcher,
        dl: DataLayer,
    ) -> None:
        self._dispatcher = dispatcher
        self._dl = dl

    def process(self, activity_id: str) -> VultronEvent | None:
        """Rehydrate + extract + dispatch one activity.

        Returns the VultronEvent if the activity was dispatched, or None
        if it was deferred or an error prevented dispatch.
        """
        ...


def build_test_pipeline(dl: DataLayer) -> InboxPipeline:
    """Construct a pipeline with real production wiring for test use.

    Uses DirectActivityDispatcher with the real use_case_map() and the
    same port factories that make_dispatcher() uses, so that routing-
    safety-net tests fail immediately on registry use-case gaps.
    """
    ...
```

---
