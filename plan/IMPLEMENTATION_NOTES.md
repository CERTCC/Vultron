## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

---

### 2026-04-08 Plan refresh #72 gap analysis

**Test suite**: 1262 tests passing (refresh #72). No warnings, no
ResourceWarnings. All linters clean.

**D5-6-AUTOENG completed (2026-04-08)**: Invitation acceptance now
auto-advances the invitee to RM.ACCEPTED and queues `RmEngageCaseActivity`
without a separate trigger. Three-actor and multi-vendor demos no longer
issue manual `engage-case` calls. D5-6-CASEPROP is now focused solely on
`EmitCreateCaseActivity` (`create_case` BT) missing `to` field and full
case embedding.

**D5-6-EMBARGORCP dependency clarification**: Per `notes/protocol-event-cascades.md`,
Option 2 (remove standalone `Announce(embargo)`, rely on `Create(Case)`)
is recommended and is independent of IDEA-260408-01 ordering. Alternatively,
it can be deferred until IDEA-260408-01-4 removes `InitializeDefaultEmbargoNode`
from `validate_tree.py` entirely. The plan has been updated to capture both
paths.

**SYNC spec and CLP spec expansion (2026-04-08)**: `specs/case-log-processing.md`
(CLP) and `specs/sync-log-replication.md` were significantly expanded with
new requirements for:

- `CaseLogEntry` model fields: `log_index`, `disposition`, `term`
- Assertion intake path (CLP-01): ordinary inbound activities as participant
  assertions; CaseActor as sole canonical log writer
- Local audit log vs. replicated canonical chain (CLP-03, CLP-04)
- Canonical serialization for hash computation (SYNC-01-005; RFC 8785 JCS)
- Commit discipline (SYNC-09): emit-after-commit invariant
- Leadership guard port in BT bridge (SYNC-09-003)
SYNC-1 task description updated in IMPLEMENTATION_PLAN.md to capture all of
these. The old note about `prev_log_index` in SYNC-2 has been corrected to
`prev_log_hash` to match the hash-chain design.

**BUG-2026040102 (circular import in test_performance.py)**: Marked FIXED
2026-04-01 in BUGS.md. Test confirmed passing in isolation as of 2026-04-08.
Resolution section was never written; fix was applied as part of the April 1
multi-vendor demo work. BUGS.md updated with resolution note.

**Testing note (2026-04-08)**: When tests need to persist actor records
through `DataLayer.create`, use a concrete actor subtype such as
`as_Organization` rather than the base `as_Actor`; the base type's optional
`type_` conflicts with the `PersistableModel` protocol under pyright.

**CONFIG-1 (YAML config)**: IDEA-260402-01 (from `plan/IDEAS.md`) has been
added as a new PRIORITY-350 task. `pyyaml` is already a transitive dependency
(from docker-compose YAML parsing). The task is independent and can be
implemented any time after D5-7 sign-off.

**IDEA-260402-02 (per-participant case replica)**: Design captured in
`plan/IDEAS.md`. Implementation is the participant-side receive path for
`Announce(CaseLogEntry)` replication; this is SYNC-2 scope. Added to
Deferred section of IMPLEMENTATION_PLAN.md for visibility.

---

### 2026-04-09 EMBARGO-DUR-1 completed

`EmbargoPolicy` now uses `timedelta` internally and ISO 8601 duration strings
at the wire layer. Key notes:

- `isodate.parse_duration("P2W")` returns `timedelta(weeks=2)` — a
  `timedelta` — so week rejection requires an explicit pre-check for `W` in
  the date part of the duration string before calling `isodate`.
- `isodate.parse_duration("P1Y")` returns `isodate.Duration` (not `timedelta`)
  so year/month rejection is handled by checking `isinstance(parsed, timedelta)`.
- `object_to_record()` serializes `timedelta` fields as ISO 8601 strings
  (via `field_serializer(when_used="json")`). The DataLayer round-trip
  works correctly because `TinyDbDataLayer` stores serialized JSON and
  `model_validate` re-parses via the `field_validator`.
- Test helpers that pass ISO 8601 strings to `EmbargoPolicy(...)` must use
  `cast(Any, EmbargoPolicy)(...)` to satisfy mypy (field is typed `timedelta`
  but Pydantic accepts strings at runtime via the `field_validator`).

---

### 2026-04-11 SYNC-1 completed

**`CaseLogEntry` / `CaseEventLog`**:

- `CaseLogEntry` is a plain Pydantic `BaseModel` (not frozen).
  Immutability of the append-only log is enforced by `CaseEventLog`; the
  model itself is not frozen so that the `model_validator` can compute
  `entry_hash` via `model_validator(mode="after")` without hitting a
  frozen-model assignment error.
- `entry_hash` is excluded from the content that is hashed (to avoid a
  self-referential dependency). The `_hashable_dict()` method explicitly
  lists the fields included in the canonical form; adding new fields
  requires updating both `_hashable_dict()` and existing log data
  (hash-chain break risk).
- Canonical serialisation uses `json.dumps(sort_keys=True, separators=(',', ':'),
  default=str)` — RFC 8785 JCS-compatible and Merkle-tree forward-compatible
  (SYNC-01-005). `default=str` handles `datetime` and enum values.
- `tail_hash` is based on the last **recorded** entry only; rejected entries do
  not advance the hash chain for replication purposes (CLP-04-003).
- `verify_chain()` validates: hash integrity of each entry, correct
  `prev_log_hash` linkage for recorded entries, and sequential `log_index`.

**BTBridge leadership guard**:

- `is_leader` is an injectable `Callable[[], bool]`; single-node default
  always returns `True`. The seam is there for multi-node Raft; the default
  imposes zero runtime cost on existing code.
- Existing callers of `BTBridge(datalayer=...)` are unaffected since
  `is_leader` is a keyword-only argument with a default.

**Next step**: SYNC-2 — one-way log replication to Participant Actors via
`Announce(CaseLogEntry)`. Prereqs: SYNC-1 ✅, OUTBOX-MON-1 ✅,
D5-7-TRIGNOTIFY-1 ✅.

---

### 2026-04-13 Priority 325 — SQLModel/SQLite DataLayer (DL-SQLITE-*)

ADR written (`docs/adr/0016-sqlmodel-sqlite-datalayer.md`). Design notes in
`notes/datalayer-sqlite-design.md`.

#### Implementation notes for DL-SQLITE-1 (`datalayer_sqlite.py`)

**Tables** (define in `datalayer_sqlite.py`, adapter layer only):

```python
class VultronObjectRecord(SQLModel, table=True):
    __tablename__ = "vultron_objects"
    id_: str = Field(primary_key=True)
    type_: str = Field(index=True)
    actor_id: str | None = Field(default=None, index=True)
    data: dict = Field(sa_column=Column(JSON))

class QueueEntry(SQLModel, table=True):
    __tablename__ = "vultron_queue"
    id: int | None = Field(default=None, primary_key=True)
    actor_id: str = Field(index=True)
    queue: str = Field(index=True)   # "inbox" or "outbox"
    activity_id: str
```

One table covers both inbox and outbox (differentiated by `queue` column).

**Engine creation** — always pass `connect_args={"check_same_thread": False}`.
For `sqlite:///:memory:` use `poolclass=StaticPool` so all connections in the
same engine share the same in-memory DB:

```python
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

def _make_engine(db_url: str) -> Engine:
    kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if db_url == "sqlite:///:memory:":
        kwargs["poolclass"] = StaticPool
    return create_engine(db_url, **kwargs)
```

**Constructor**:

```python
class SqliteDataLayer:
    def __init__(
        self,
        db_url: str = "sqlite:///:memory:",
        actor_id: str | None = None,
    ) -> None:
        self._engine = _make_engine(db_url)
        self._actor_id = actor_id
        SQLModel.metadata.create_all(self._engine)
```

Each `SqliteDataLayer("sqlite:///:memory:")` call creates an independent
in-memory DB — no patching needed for test isolation. Test fixtures that
previously did `TinyDbDataLayer(db_path=None)` become
`SqliteDataLayer("sqlite:///:memory:")`.

**Serialization**: reuse `Record.from_obj` / `Record.to_obj` from `db_record.py`:

```python
from vultron.adapters.driven.db_record import Record, record_to_object

def _to_row(self, obj: PersistableModel) -> VultronObjectRecord:
    rec = Record.from_obj(obj)
    return VultronObjectRecord(
        id_=rec.id_, type_=rec.type_,
        actor_id=self._actor_id, data=rec.data_,
    )

def _from_row(self, row: VultronObjectRecord) -> PersistableModel | None:
    rec = Record(id_=row.id_, type_=row.type_, data_=row.data)
    try:
        return cast(PersistableModel, record_to_object(rec))
    except (ValueError, ValidationError):
        return None
```

**Actor scoping** — add helper:

```python
def _scoped(self, stmt):
    if self._actor_id:
        return stmt.where(VultronObjectRecord.actor_id == self._actor_id)
    return stmt
```

Apply `_scoped()` to all `select(VultronObjectRecord)` queries in `read`,
`get`, `all`, `by_type`, etc.

**`record_outbox_item`** writes to an arbitrary actor's outbox (cross-actor):

```python
def record_outbox_item(self, actor_id: str, activity_id: str) -> None:
    with Session(self._engine) as session:
        session.add(QueueEntry(actor_id=actor_id, queue="outbox",
                               activity_id=activity_id))
        session.commit()
```

This bypasses `self._actor_id` — intentional, same as TinyDB's direct
`self._db.table(f"{actor_id}_outbox")` access.

**`get_all_actor_datalayers`** — with SQLite, actors are not tracked by
instance registry. The clean replacement returns the module-level
`_actor_instances` dict (same as TinyDB). The outbox monitor iterates this
dict; any actor that has had `get_datalayer(actor_id=X)` called is included.

**`reset_datalayer`** — drop and recreate all tables on the shared engine(s),
then clear the instance caches. For `:memory:` this gives a fresh empty DB:

```python
def reset_datalayer(actor_id: str | None = None) -> None:
    global _shared_instance, _actor_instances
    engines_to_reset: set[Engine] = set()
    if actor_id is None:
        if _shared_instance:
            engines_to_reset.add(_shared_instance._engine)
        for inst in _actor_instances.values():
            engines_to_reset.add(inst._engine)
        _shared_instance = None
        _actor_instances = {}
    else:
        if actor_id in _actor_instances:
            engines_to_reset.add(_actor_instances.pop(actor_id)._engine)
    for engine in engines_to_reset:
        SQLModel.metadata.drop_all(engine)
        SQLModel.metadata.create_all(engine)
```

**`count_all`** — use SQLAlchemy `func.count()`:

```python
from sqlalchemy import func
rows = session.exec(
    select(VultronObjectRecord.type_, func.count())
    .group_by(VultronObjectRecord.type_)
).all()
```

**`find_actor_by_short_id`** — query `type_` IN actor types, filter in Python
on `id_` suffix (same logic as TinyDB version but over a single table):

```python
ACTOR_TYPES = {"Actor", "Person", "Organization", "Service", "Application", "Group"}
stmt = select(VultronObjectRecord).where(
    VultronObjectRecord.type_.in_(ACTOR_TYPES)
)
if self._actor_id:
    stmt = stmt.where(VultronObjectRecord.actor_id == self._actor_id)
for row in session.exec(stmt):
    if row.id_.endswith(f"/{short_id}") or row.id_ == short_id:
        ...
```

**`find_case_by_report_id`** — filter on `type_ = "VulnerabilityCase"`, then
iterate `data["vulnerability_reports"]` in Python (same as TinyDB). SQLite
JSON path operators could be used for a future optimisation but Python-side
filtering is acceptable at prototype scale.

#### DL-SQLITE-2: factory + env var + rehydration.py

New module `vultron/adapters/driven/datalayer.py` re-exports
`SqliteDataLayer`, `get_datalayer`, `reset_datalayer`, `get_all_actor_datalayers`
so all callers can switch to a single stable import path without referencing
`_sqlite` or `_tinydb` in the module name:

```python
# vultron/adapters/driven/datalayer.py
from vultron.adapters.driven.datalayer_sqlite import (  # noqa: F401
    SqliteDataLayer as DataLayerImpl,
    get_datalayer,
    reset_datalayer,
    get_all_actor_datalayers,
)
```

All callers in `vultron/adapters/driving/` should be updated to
`from vultron.adapters.driven.datalayer import get_datalayer`.

**`VULTRON_DB_PATH` → `VULTRON_DB_URL`**: the new env var is a full
SQLAlchemy connection string. Default: `sqlite:///mydb.sqlite`.
Read at module import time in `datalayer_sqlite.py`:

```python
_DEFAULT_DB_URL: str = os.environ.get("VULTRON_DB_URL", "sqlite:///mydb.sqlite")
```

**`rehydration.py` (TECHDEBT-32c)**: current code has a fallback:

```python
# in wire/as2/rehydration.py  — REMOVE THIS:
try:
    from vultron.adapters.driven.datalayer_tinydb import get_datalayer
    ...
except ImportError:
    pass
```

Replace with a required `dl: DataLayer` parameter (no fallback). Any callers
that pass `dl=None` or rely on the fallback must be updated to pass a real
DataLayer. Check all call sites first with `grep -rn "rehydrate(" vultron/`.

#### DL-SQLITE-3: test infrastructure

`test/conftest.py` replacement — remove `pytest_configure` patch entirely;
add a simple env-var default at module level:

```python
import os
os.environ.setdefault("VULTRON_DB_URL", "sqlite:///:memory:")
```

Remove `cleanup_test_db_files` fixture (no `mydb.json` created).

The `test/demo/conftest.py` `reset_datalayer_between_modules` fixture becomes:

```python
from vultron.adapters.driven.datalayer import reset_datalayer
# fixture body unchanged
```

For all test files that do `TinyDbDataLayer(db_path=None)`:

```python
# Before:
from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
return TinyDbDataLayer(db_path=None)

# After:
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
return SqliteDataLayer("sqlite:///:memory:")
```

`test/adapters/driven/test_tinydb_backend.py` should be renamed and updated
to `test_sqlite_backend.py`; existing tests remain valid since the DataLayer
Protocol is unchanged.

#### DL-SQLITE-4: delete TinyDB

After all callers are migrated:

```bash
uv remove tinydb
rm vultron/adapters/driven/datalayer_tinydb.py
```

Check `pyproject.toml` `[tool.pytest.ini_options]` for any TinyDB references.
Search for residual `tinydb` strings: `grep -rn tinydb vultron/ test/ docs/`.

#### DL-SQLITE-5: Docker

```yaml
# docker-compose-multi-actor.yml — replace all VULTRON_DB_PATH occurrences:
- VULTRON_DB_URL=sqlite:////app/data/mydb.sqlite
```

`docker/README.md` table row:

```markdown
| `VULTRON_DB_URL` | `sqlite:////app/data/mydb.sqlite` | SQLAlchemy connection URL for the DataLayer |
```

(Four slashes: `sqlite:////app/...` = absolute path `/app/...`.)

Also update the comment block near line 36 of `docker-compose-multi-actor.yml`.

---

### 2026-04-13 DL-SQLITE session handoff checklist

This is the current active implementation plan for Priority 325. The ADR is
already written, but no code has been changed yet in this session. The notes
below capture the concrete execution order, the files that must change, and the
small compatibility traps found during codebase review.

#### Current status snapshot

- `docs/adr/0016-sqlmodel-sqlite-datalayer.md` already exists. Treat
  DL-SQLITE-ADR as complete once `IMPLEMENTATION_PLAN.md` is updated.
- `vultron/adapters/driven/datalayer_sqlite.py` does not exist yet.
- `vultron/wire/as2/rehydration.py` already appears to use explicit `dl`
  injection; no TinyDB fallback import was found during spot-checking.
- The remaining work is DL-SQLITE-1 through DL-SQLITE-5.

#### Important implementation decision

Use **separate** `InboxEntry` and `OutboxEntry` SQLModel tables, not the
earlier single `QueueEntry` draft shown above. The ADR, design note, and
`IMPLEMENTATION_PLAN.md` all describe separate inbox/outbox tables, so that
should be treated as the authoritative direction.

#### Recommended execution order

1. Add the new dependency and implement the SQLite adapter.
2. Add the stable datalayer facade module and switch production imports.
3. Convert the test infrastructure and test imports/usages.
4. Remove TinyDB and its dependency only after all callers are migrated.
5. Update Docker env var references and docs.
6. Update `IMPLEMENTATION_PLAN.md` and append to
   `plan/IMPLEMENTATION_HISTORY.md`.
7. Run formatters, linters, and the unit test suite once.

#### Step 1: add dependency and create the adapter

1. Run `uv add sqlmodel`.
2. Create `vultron/adapters/driven/datalayer_sqlite.py`.
3. Define:
   - `VultronObjectRecord`
   - `InboxEntry`
   - `OutboxEntry`
4. Add `_make_engine(db_url: str) -> Engine`:
   - always set `connect_args={"check_same_thread": False}`
   - for `sqlite:///:memory:` also set `poolclass=StaticPool`
5. Implement `SqliteDataLayer` with constructor:
   - `db_url: str = "sqlite:///:memory:"`
   - `actor_id: str | None = None`
   - `SQLModel.metadata.create_all(self._engine)` on init
6. Reuse `Record` / `object_to_record` / `record_to_object` from
   `vultron/adapters/driven/db_record.py`; do not duplicate vocabulary lookup.
7. Match the current `DataLayer` Protocol exactly:
   - `create`
   - `read`
   - `get`
   - `get_all`
   - `update`
   - `save`
   - `delete`
   - `all`
   - `count_all`
   - `by_type`
   - `clear_table`
   - `clear_all`
   - `ping`
   - `exists`
   - `inbox_append`, `inbox_list`, `inbox_pop`
   - `outbox_append`, `outbox_list`, `outbox_pop`
   - `record_outbox_item`
   - `find_actor_by_short_id`
   - `find_case_by_report_id`
8. Preserve TinyDB compatibility behaviour where it matters:
   - `read()` should retry bare UUIDs as `urn:uuid:<uuid>`
   - actor-scoped instances must filter by `actor_id`
   - shared/admin instance must see all actors
   - `record_outbox_item(actor_id, ...)` must bypass the instance scope and
     write directly to the target actor's outbox queue
9. Implement module-level factory helpers in the same file:
   - `_shared_instance`
   - `_actor_instances`
   - `get_datalayer(actor_id: str | None = None, db_url: str | None = None)`
   - `get_all_actor_datalayers()`
   - `reset_datalayer(actor_id: str | None = None)`
10. Use `VULTRON_DB_URL`, defaulting to `sqlite:///mydb.sqlite`.

#### Step 2: add stable facade and switch production imports

1. Create `vultron/adapters/driven/datalayer.py`.
2. Re-export:
   - `SqliteDataLayer as DataLayerImpl`
   - `get_datalayer`
   - `reset_datalayer`
   - `get_all_actor_datalayers`
3. Update these production files to import from
   `vultron.adapters.driven.datalayer`:
   - `vultron/adapters/driving/cli.py`
   - `vultron/adapters/driving/fastapi/app.py`
   - `vultron/adapters/driving/fastapi/main.py`
   - `vultron/adapters/driving/fastapi/outbox_monitor.py`
   - `vultron/adapters/driving/fastapi/routers/actors.py`
   - `vultron/adapters/driving/fastapi/routers/datalayer.py`
   - `vultron/adapters/driving/fastapi/routers/health.py`
   - `vultron/adapters/driving/fastapi/routers/info.py`
   - `vultron/adapters/driving/fastapi/routers/trigger_case.py`
   - `vultron/adapters/driving/fastapi/routers/trigger_embargo.py`
   - `vultron/adapters/driving/fastapi/routers/trigger_report.py`
   - `vultron/adapters/driving/fastapi/routers/trigger_sync.py`
   - `vultron/adapters/driving/mcp_server.py`
4. Update `vultron/adapters/driving/fastapi/outbox_monitor.py` typing from
   `TinyDbDataLayer` to either `SqliteDataLayer` or the `DataLayer` Protocol.

#### Step 3: convert the test infrastructure

1. Replace top-level `test/conftest.py` TinyDB patching with:

   ```python
   import os
   os.environ.setdefault("VULTRON_DB_URL", "sqlite:///:memory:")
   ```

2. Remove:
   - `pytest_configure`
   - the `TinyDbDataLayer.__init__` monkey-patch
   - `cleanup_test_db_files`
3. Update `test/demo/conftest.py` to import `reset_datalayer` from the new
   facade module.
4. Rewrite `test/adapters/driven/conftest.py`:
   - remove the patch-management fixture entirely
   - replace file-backed TinyDB fixtures with SQLite fixtures
   - keep any integration fixture that intentionally uses a real file-backed
     SQLite URL
5. Rename `test/adapters/driven/test_tinydb_backend.py` to
   `test_sqlite_backend.py`.
6. Update the following test files that still reference TinyDB symbols or
   `VULTRON_DB_PATH`:
   - `test/adapters/driven/conftest.py`
   - `test/adapters/driven/test_datalayer_isolation.py`
   - `test/adapters/driven/test_delivery_inbox_url.py`
   - `test/adapters/driven/test_get_datalayer.py`
   - `test/adapters/driven/test_tinydb_backend.py`
   - `test/adapters/driving/fastapi/conftest.py`
   - `test/adapters/driving/fastapi/routers/conftest.py`
   - `test/adapters/driving/fastapi/routers/test_datalayer_serialization.py`
   - `test/adapters/driving/fastapi/routers/test_health.py`
   - `test/adapters/driving/fastapi/routers/test_info.py`
   - `test/adapters/driving/fastapi/routers/test_trigger_case.py`
   - `test/adapters/driving/fastapi/routers/test_trigger_embargo.py`
   - `test/adapters/driving/fastapi/routers/test_trigger_report.py`
   - `test/adapters/driving/fastapi/routers/test_trigger_sync.py`
   - `test/conftest.py`
   - `test/core/behaviors/case/test_bug_26040902_regression.py`
   - `test/core/behaviors/case/test_create_tree.py`
   - `test/core/behaviors/case/test_receive_report_case_tree.py`
   - `test/core/behaviors/report/test_nodes.py`
   - `test/core/behaviors/report/test_prioritize_tree.py`
   - `test/core/behaviors/report/test_validate_tree.py`
   - `test/core/behaviors/test_bridge.py`
   - `test/core/behaviors/test_helpers.py`
   - `test/core/use_cases/query/test_action_rules.py`
   - `test/core/use_cases/received/test_actor.py`
   - `test/core/use_cases/received/test_case_participant.py`
   - `test/core/use_cases/received/test_case.py`
   - `test/core/use_cases/received/test_embargo.py`
   - `test/core/use_cases/received/test_note.py`
   - `test/core/use_cases/received/test_reject_sync.py`
   - `test/core/use_cases/received/test_report.py`
   - `test/core/use_cases/received/test_status.py`
   - `test/core/use_cases/received/test_sync.py`
   - `test/core/use_cases/test_reporting_workflow.py`
   - `test/core/use_cases/triggers/test_note_trigger.py`
   - `test/core/use_cases/triggers/test_trignotify.py`
   - `test/demo/conftest.py`
   - `test/test_datalayer_in_memory.py`
   - `test/wire/as2/vocab/test_case_event.py`
   - `test/wire/as2/vocab/test_embargo_policy.py`
7. Replace `TinyDbDataLayer(db_path=None)` usages with
   `SqliteDataLayer("sqlite:///:memory:")`.
8. Replace file-backed TinyDB tests with file-backed SQLite URLs, for example
   `sqlite:///.../test.sqlite`.

#### Step 4: remove TinyDB

1. Delete `vultron/adapters/driven/datalayer_tinydb.py`.
2. Run `uv remove tinydb`.
3. Search for residual strings:
   - `datalayer_tinydb`
   - `TinyDbDataLayer`
   - `tinydb`
   - `VULTRON_DB_PATH`

#### Step 5: Docker and docs

1. Update `docker/docker-compose-multi-actor.yml`.
2. Replace every `VULTRON_DB_PATH` with:

   ```text
   VULTRON_DB_URL=sqlite:////app/data/mydb.sqlite
   ```

3. Update the nearby explanatory comments in that compose file.
4. Update `docker/README.md` to document `VULTRON_DB_URL`.

#### Step 6: plan bookkeeping

1. Update `plan/IMPLEMENTATION_PLAN.md`:
   - mark DL-SQLITE-ADR complete
   - mark DL-SQLITE-1 through DL-SQLITE-5 complete when done
   - fix any stale summary text that still implies Priority 320 is active
2. Append a short completion note to `plan/IMPLEMENTATION_HISTORY.md`.

#### Validation checklist after implementation

1. Run:

   ```bash
   uv run black vultron/ test/ && uv run flake8 vultron/ test/
   ```

2. Run:

   ```bash
   uv run mypy && uv run pyright
   ```

3. Run the unit suite once:

   ```bash
   uv run pytest --tb=short 2>&1 | tail -5
   ```

#### Small code-reading notes from exploration

- `test/demo/test_two_actor_demo.py` patches
  `vultron.demo.two_actor_demo.reset_datalayer`; that patch target is part of
  the demo module and does not need a path rename during this migration.
- `test/adapters/driven/test_get_datalayer.py` is currently TinyDB-specific and
  must be rewritten around `VULTRON_DB_URL`, singleton behaviour, and
  file-backed SQLite URLs.
- `vultron/adapters/driving/fastapi/routers/actors.py` and
  `vultron/adapters/driving/fastapi/routers/info.py` currently expect
  `get_all()` to return raw record dicts with `id_`, `type_`, and `data_`.
  Preserve that return shape in the SQLite adapter.
- `vultron/adapters/driving/fastapi/outbox_monitor.py` imports
  `TinyDbDataLayer` only for typing and factory defaults; it should be updated
  to a backend-neutral type while keeping current behaviour unchanged.
