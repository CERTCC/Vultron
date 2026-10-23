---
source: NOTES-inbox-pipeline--factory-fixture-pattern
timestamp: '2026-09-17T17:25:24.422394+00:00'
title: Factory and Fixture Pattern
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) build_test_pipeline() + conftest fixture exist
**Superseded by:** vultron/adapters/driving/fastapi/inbox_pipeline.py; test conftest

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
    # `actor_id` is mandatory — no DataLayer is unscoped (ADR-0073, DL-07-002).
    dl = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://example.org/actors/vendor",
    )
    pipeline = build_test_pipeline(dl)
    return pipeline, dl
```

---
