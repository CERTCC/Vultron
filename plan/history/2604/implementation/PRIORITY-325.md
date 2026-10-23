---
title: "PRIORITY-325 \u2014 TinyDB to SQLModel/SQLite DataLayer Migration\
  \ (DL-SQLITE-ADR through DL-SQLITE-5)"
type: implementation
timestamp: '2026-04-14T00:00:00+00:00'
source: PRIORITY-325
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6010
legacy_heading: "PRIORITY-325 \u2014 TinyDB to SQLModel/SQLite DataLayer Migration\
  \ (DL-SQLITE-ADR through DL-SQLITE-5)"
date_source: git-blame
---

## PRIORITY-325 — TinyDB to SQLModel/SQLite DataLayer Migration (DL-SQLITE-ADR through DL-SQLITE-5)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6010`
**Canonical date**: 2026-04-14 (git blame)
**Legacy heading**

```text
PRIORITY-325 — TinyDB to SQLModel/SQLite DataLayer Migration (DL-SQLITE-ADR through DL-SQLITE-5)
```

**Completed**: 2026-07

### Summary

Replaced the TinyDB-backed `datalayer_tinydb.py` adapter with a new
SQLModel/SQLite implementation (`datalayer_sqlite.py`). All callers updated;
TinyDB fully removed from the codebase.

### Files Created

- `vultron/adapters/driven/datalayer_sqlite.py` — `SqliteDataLayer`
  implementation using SQLModel, single-table polymorphic schema
  (`VultronObjectRecord`, `QueueEntry`), actor-scoped queries,
  `get_datalayer()` factory, `reset_datalayer()`.
- `vultron/adapters/driven/datalayer.py` — Stable re-export facade.
- `test/adapters/driven/test_sqlite_backend.py` — Comprehensive unit and
  integration tests for the new backend.

### Files Deleted

- `vultron/adapters/driven/datalayer_tinydb.py`
- `test/adapters/driven/test_tinydb_backend.py`

### Key Changes

- `pyproject.toml`: removed `tinydb`, added `sqlmodel>=0.0.38`.
- `test/conftest.py`: sets `VULTRON_DB_URL=sqlite:///:memory:` before all
  imports; session-scoped `cleanup_test_datalayer` fixture calls
  `reset_datalayer()`.
- `docker/docker-compose-multi-actor.yml`: renamed env var from
  `VULTRON_DB_PATH` to `VULTRON_DB_URL`.
- 13+ `vultron/adapters/driving/` files and 30+ `test/` files: import path
  updated from `datalayer_tinydb` to `datalayer` facade.
- `get_datalayer()` reads `VULTRON_DB_URL` from `os.environ` at call time
  (not just at import time), improving test isolation.

### Notable Implementation Details

- `extend_existing=True` on SQLModel table classes prevents errors on module
  reimport.
- Custom `json_serializer` passed to `create_engine()` ensures `datetime`
  objects in JSON columns serialise as ISO-8601 strings.
- `_owns_engine` flag on `SqliteDataLayer` prevents `__del__` from disposing
  a borrowed engine when two instances share an engine for testing.
- `reset_datalayer()` drops and recreates tables but does NOT dispose engines
  (disposing an in-memory engine destroys its data).

> **Note (2026-04-14):** The description of `reset_datalayer()` above was
> superseded by the ResourceWarning fix below. It now calls `inst.close()`
> (which disposes engines) and no longer runs DDL on abandoned engines.

### Validation

- All four linters (black, flake8, mypy, pyright) pass with zero errors.
- `uv run pytest --tb=short 2>&1 | tail -5` gives
  `1402 passed, 13 skipped, 5581 subtests passed in ~20s`
