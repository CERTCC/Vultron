---
title: "Refresh #51 \u2014 VCR-014 + TECHDEBT-37 (2026-03-25)"
type: implementation
timestamp: '2026-03-25T00:00:00+00:00'
source: LEGACY-2026-03-25-refresh-51-vcr-014-techdebt-37-2026-03-25
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3117
legacy_heading: "Refresh #51 \u2014 VCR-014 + TECHDEBT-37 (2026-03-25)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-25'
---

## Refresh #51 — VCR-014 + TECHDEBT-37 (2026-03-25)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3117`
**Canonical date**: 2026-03-25 (git blame)
**Legacy heading**

```text
Refresh #51 — VCR-014 + TECHDEBT-37 (2026-03-25)
```

**Legacy heading dates**: 2026-03-25

### Tasks completed

- **VCR-014**: Removed `vultron/api/v2/data/actor_io.py`. The global in-memory
  `ACTOR_IO_STORE` is fully superseded by the DataLayer inbox/outbox methods
  (`inbox_list/pop/append`, `outbox_list/pop/append`) added in ACT-2.
  Removed the `init_actor_io` import and call from all test fixtures.
  Deleted `test/api/v2/data/test_actor_io.py` and `test/api/v2/data/conftest.py`.

- **TECHDEBT-37**: Migrated all tests from `test/api/` to the canonical layout:
  - `test/api/v2/backend/test_inbox_handler.py` →
    `test/adapters/driving/fastapi/test_inbox_handler.py`
  - `test/api/v2/backend/test_outbox.py` →
    `test/adapters/driving/fastapi/test_outbox.py`
  - `test/api/v2/backend/test_trigger_services.py` →
    `test/adapters/driving/fastapi/test_trigger_services.py`
  - `test/api/v2/conftest.py` →
    `test/adapters/driving/fastapi/conftest.py`
  - `test/api/v2/test_v2_api.py` →
    `test/adapters/driving/fastapi/test_api.py`
  - `test/api/v2/routers/conftest.py` →
    `test/adapters/driving/fastapi/routers/conftest.py`
  - `test/api/v2/routers/test_actors.py` →
    `test/adapters/driving/fastapi/routers/test_actors.py`
  - `test/api/v2/routers/test_datalayer_serialization.py` →
    `test/adapters/driving/fastapi/routers/test_datalayer_serialization.py`
  - `test/api/v2/routers/test_datalayer.py` →
    `test/adapters/driving/fastapi/routers/test_datalayer.py`
  - `test/api/v2/routers/test_health.py` →
    `test/adapters/driving/fastapi/routers/test_health.py`
  - `test/api/v2/routers/test_trigger_{report,case,embargo}.py` →
    `test/adapters/driving/fastapi/routers/test_trigger_{report,case,embargo}.py`
  - `test/api/v2/datalayer/conftest.py` →
    `test/adapters/driven/conftest.py`
  - `test/api/v2/datalayer/test_db_record.py` →
    `test/adapters/driven/test_db_record.py`
  - `test/api/v2/datalayer/test_tinydb_backend.py` →
    `test/adapters/driven/test_tinydb_backend.py`
  - `test/api/test_reporting_workflow.py` →
    `test/core/use_cases/test_reporting_workflow.py`
  - `test/api/` directory removed.

### Files modified

- `vultron/api/v2/data/actor_io.py`: deleted
- `test/api/` directory: deleted (all tests relocated)
- `test/adapters/driving/` directory: created with `__init__.py`
- `test/adapters/driving/fastapi/` directory: created with all migrated tests
- `test/adapters/driving/fastapi/routers/` directory: created with all
  migrated router tests
- `test/adapters/driven/conftest.py`: created (from datalayer/conftest.py)
- `test/adapters/driven/test_db_record.py`: created
- `test/adapters/driven/test_tinydb_backend.py`: created
- `test/core/use_cases/test_reporting_workflow.py`: created

### Test results

998 passed, 5581 subtests passed.
