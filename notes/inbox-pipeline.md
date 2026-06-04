---
title: Inbox Pipeline — InboxPipeline Design Notes
status: active
description: >
  Design decisions, implementation guidance, and test patterns for the
  `InboxPipeline` class and `build_test_pipeline()` factory that surface
  the `inbox_handler → dispatcher` seam as a testable unit.
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

## Context

`vultron/adapters/driving/fastapi/inbox_handler.py` implements the full inbox
processing pipeline:

```text
inbox queue (activity ID string)
  → rehydrate(id, dl)              # fetch + reconstruct full AS2 object
  → extract_event(activity)        # AS2 → domain VultronEvent
  → _dispatch_or_defer_inbox_item  # check case context, maybe defer
  → dispatcher.dispatch(event, dl) # route to use-case
  → use_case.execute()
```

All existing unit tests mock either `_DISPATCHER` or `prepare_for_dispatch`.
No unit test exercises the real chain end-to-end. That flow is covered only
by slow demo integration tests in `test/demo/`.

**The risk**: if a new semantic type is added but its `USE_CASE_MAP` registration
is forgotten, all mock-based unit tests pass and the failure only surfaces in
production or the slow integration suite.

---

## Decision Table

| Question | Decision | Rationale |
|----------|----------|-----------|
| Which pipeline path to wrap? | Full `_process_inbox_item` path | Surfaces deferral and error-requeue — the untested behaviors listed in the RFC |
| Where should the class live? | `vultron/adapters/driving/fastapi/inbox_pipeline.py` | Co-located with `inbox_handler.py`; avoids a new layer |
| Return type of `process()`? | `VultronEvent \| None` | `None` = clean signal that dispatch did not occur (deferred or error) |
| Should `_DISPATCHER` global change? | No — pipeline is additive | `InboxPipeline` is a parallel path; production lifespan wiring is unchanged |
| Factory function vs. fixture? | Both | Module-level `build_test_pipeline()` + `conftest.py` pytest fixture |
| ADR needed? | No | Purely additive; no evaluated alternative was rejected (MS-11-005) |
| Spec ID prefix? | `IBP` in `specs/inbox-pipeline.yaml` | Self-contained spec for the pipeline contract |
| Test coverage scope? | One routing-safety-net test per semantic domain | ~7 tests catch registration gaps without full enum-value matrix |

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
    safety-net tests fail immediately on USE_CASE_MAP registration gaps.
    """
    ...
```

---

## Factory and Fixture Pattern

### Module-level factory (in `inbox_pipeline.py`)

```python
def build_test_pipeline(dl: DataLayer) -> InboxPipeline:
    from vultron.adapters.driving.fastapi.inbox_handler import (
        _sync_port_factory,
        _trigger_activity_port_factory,
        make_dispatcher,
    )
    dispatcher = make_dispatcher()  # real use_case_map() + port factories
    return InboxPipeline(dispatcher=dispatcher, dl=dl)
```

### pytest fixture (in `test/adapters/driving/fastapi/conftest.py`)

```python
import pytest
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_pipeline import (
    InboxPipeline,
    build_test_pipeline,
)

@pytest.fixture
def test_pipeline() -> tuple[InboxPipeline, SqliteDataLayer]:
    dl = SqliteDataLayer("sqlite:///:memory:")
    pipeline = build_test_pipeline(dl)
    return pipeline, dl
```

---

## Routing-Safety-Net Test Pattern

One test per semantic domain. Each test:

1. Constructs the required domain objects with full URIs
2. Saves them to the in-memory DataLayer
3. Calls `pipeline.process(activity.id_)`
4. Asserts `event.semantic_type == MessageSemantics.<EXPECTED>`
5. Asserts the expected DataLayer side effect occurred

```python
def test_create_report_routes_correctly(test_pipeline):
    pipeline, dl = test_pipeline

    report = VulnerabilityReport(
        id_="https://example.org/reports/r-1", ...
    )
    activity = rm_create_report_activity(
        report=report,
        actor="https://example.org/actors/reporter",
        to=["https://example.org/actors/coordinator"],
    )
    dl.save(report)
    dl.save(activity)

    event = pipeline.process(activity.id_)

    assert event is not None
    assert event.semantic_type == MessageSemantics.CREATE_REPORT
    # assert expected DataLayer side effect
    assert dl.read(report.id_) is not None
```

### Semantic domains and representative test cases

| Domain | Representative semantic type | Key side effect to assert |
|--------|------------------------------|--------------------------|
| Report | `CREATE_REPORT` | Report saved in DataLayer |
| Case | `ANNOUNCE_VULNERABILITY_CASE` | Case saved or deferred |
| Embargo | `OFFER_EMBARGO` | Embargo offer recorded |
| Note | `CREATE_NOTE` | Note attached to case |
| Actor | `ANNOUNCE_ACTOR` | Actor profile saved |
| Status | `ANNOUNCE_CASE_STATUS` | Case status updated |
| Sync | `ANNOUNCE_LOG_ENTRY` | Log entry persisted |

### Deferral path test pattern

```python
def test_activity_with_unknown_case_is_deferred(test_pipeline):
    pipeline, dl = test_pipeline
    # activity referencing a case not yet in dl
    ...
    result = pipeline.process(activity.id_)

    assert result is None  # not dispatched
    # activity ID appears in pending-case inbox
    pending = dl.get("pending_case_inbox", ...)
    assert activity.id_ in pending
```

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

## Migration Guide for Existing Tests

Existing mock-based tests in
`test/adapters/driving/fastapi/test_inbox_handler.py` remain valid for
fast unit coverage of `inbox_handler.py` internals. Do **not** delete them.

New routing-safety-net tests go in the separate
`test/adapters/driving/fastapi/test_inbox_pipeline.py` file. They
complement, not replace, the mock-based tests.

```text
test/adapters/driving/fastapi/
  test_inbox_handler.py       # existing — keep as-is
  test_inbox_pipeline.py      # new — routing safety net
  conftest.py                 # add test_pipeline fixture here
```
