# SQLModel/SQLite DataLayer Design

**Status**: Planned — Priority 325 (`plan/IMPLEMENTATION_PLAN.md`
Phase PRIORITY-325).

**Replaces**: `TinyDbDataLayer` in `vultron/adapters/driven/datalayer_tinydb.py`.

**Cross-references**: IDEA-26040902 (`plan/IDEAS.md`),
`notes/domain-model-separation.md` (DataLayer as a Port section),
`plan/PRIORITIES.md` Priority 325.

---

## Why SQLite over TinyDB

TinyDB rewrites the entire JSON file on every read **and** write operation.
This produces O(n) I/O cost proportional to *total database size*, not query
size. BUG-2026041001 (April 2026) made this concrete: the test suite grew from
~13 seconds to 15+ minutes as test coverage expanded. The fix required a
`pytest_configure` monkey-patch to force `MemoryStorage` globally — accidental
complexity paid entirely to work around the backend, not to test application
behaviour.

SQLite via SQLModel gives row-level I/O (cost proportional to the query, not
the file), proper transactions, and idiomatic test isolation via
`sqlite:///:memory:` — with no patching of application code.

MongoDB remains a future upgrade path for production/sharding scenarios, but
is unnecessary for prototype-phase work where a local file suffices.

---

## Storage Schema

The adapter uses **three SQLModel tables**, all defined in the adapter layer.
Domain models (`vultron/core/`, `vultron/wire/`) are not modified.

### `VultronObjectRecord` — universal object storage

```python
class VultronObjectRecord(SQLModel, table=True):
    __tablename__ = "vultron_objects"

    id_: str = Field(primary_key=True)
    type_: str = Field(index=True)        # AS2 type name; replaces per-type table routing
    actor_id: str | None = Field(default=None, index=True)  # actor scoping
    data: dict = Field(sa_column=Column(JSON))  # full model_dump(by_alias=True)
```

All Vultron domain objects are stored as a single JSON blob in `data`.
The `type_` and `actor_id` columns are denormalized for indexed queries.
This is intentionally document-oriented and maps naturally to a future
MongoDB collection.

### `InboxEntry` / `OutboxEntry` — message queues

```python
class InboxEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    actor_id: str = Field(index=True)
    activity_id: str

class OutboxEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    actor_id: str = Field(index=True)
    target_actor_id: str | None = None
    activity_id: str
```

Simple append-only queues; `inbox_pop()` / `outbox_pop()` delete the returned
row after retrieval.

---

## Actor Scoping

The existing `TinyDbDataLayer` uses a `{actor_id}_{table_name}` table-name
prefix to isolate each actor's data. The SQLite adapter replicates this
semantics with an `actor_id` column index:

- An actor-scoped `SqliteDataLayer` (created by `get_datalayer(actor_id=...)`)
  adds `WHERE actor_id = <actor_id>` to all queries and sets `actor_id` on
  all inserts.
- The shared/admin `SqliteDataLayer` (created by `get_datalayer()`) queries
  across all actors.

This is structurally equivalent to "Option B" (namespace prefix per actor)
from the earlier TinyDB design analysis, and it maps cleanly to a future
MongoDB adapter (collection-level or document-level `actor_id` filter).

---

## Object Serialization and Deserialization

### Storing an object

```python
data = obj.model_dump(by_alias=True)
record = VultronObjectRecord(
    id_=obj.id_,
    type_=obj.type_,
    actor_id=self._actor_id,
    data=data,
)
session.add(record)
session.commit()
```

### Reconstructing a typed object from storage

The new adapter MUST reuse the existing `record_to_object` / `object_to_record`
helpers in `vultron/adapters/driven/db_record.py`. These helpers call
`find_in_vocabulary(type_name)` from the vocabulary registry to look up the
correct Pydantic subclass before calling `model_validate`.

```python
from vultron.adapters.driven.db_record import record_to_object
from vultron.core.ports.datalayer import StorableRecord

def _object_from_row(self, row: VultronObjectRecord) -> PersistableModel | None:
    stored = StorableRecord(id_=row.id_, type_=row.type_, **row.data)
    return record_to_object(stored)
```

**Do not** re-implement vocabulary lookup inline in the SQLite adapter.
The shared `db_record.py` helpers are the single source of truth for
type-safe round-trip serialization.

---

## Test Isolation Strategy

Set the connection URL to `sqlite:///:memory:` for test sessions.

**Recommended approach**: Set `VULTRON_DB_URL=sqlite:///:memory:` in the
top-level `conftest.py` (before any `SqliteDataLayer` is constructed), or
pass `sqlite:///:memory:` directly in test fixtures.

```python
# conftest.py (top-level)
import os
os.environ.setdefault("VULTRON_DB_URL", "sqlite:///:memory:")
```

Each `SqliteDataLayer` instance creates its own SQLAlchemy `Engine`. For a
`sqlite:///:memory:` URL, SQLAlchemy creates an independent in-memory database
per engine, giving automatic per-instance isolation with no patching. Unlike
TinyDB's `MemoryStorage`, this requires **no monkey-patching** and is handled
entirely through the normal constructor path.

For integration tests that require a file-backed database, pass a
`sqlite:///path/to/test.sqlite` URL explicitly and clean up the file in a
fixture teardown.

---

## Connection URL Patterns

| Environment | `VULTRON_DB_URL` value |
|---|---|
| Development (default) | `sqlite:///mydb.sqlite` |
| Docker container | `sqlite:////app/data/mydb.sqlite` |
| Test session | `sqlite:///:memory:` |
| Integration test | `sqlite:///path/to/test.db` |

The format is the standard SQLAlchemy connection URL. This makes a future
Postgres or MongoDB switch a one-line env var change (modulo a new adapter
implementation).

---

## Migration Notes

- **No data migration needed**: This is a prototype; per IDEA-26040903 no
  backward compatibility with existing `mydb.json` files is required. Existing
  `mydb.json` files are simply abandoned.
- **Env var rename**: `VULTRON_DB_PATH` → `VULTRON_DB_URL`. Update Docker env
  files and any documentation that references the old name.
- **TECHDEBT-32c absorbed**: The `datalayer_tinydb` fallback import in
  `vultron/wire/as2/rehydration.py` is removed as part of DL-SQLITE-2.
  Make `dl` a required parameter.
- **`db_record.py` is retained**: `object_to_record` and `record_to_object`
  remain in `vultron/adapters/driven/db_record.py` and are reused by the new
  adapter. Do not delete or move them.
- **`VOCAB-REG-1.1` note**: `vocabulary-registry.md` documents a migration
  note about the `datalayer_tinydb.py` caller using `if vocab_cls is not None`
  as a guard. The SQLite adapter should use the fail-fast `find_in_vocabulary`
  behaviour (raises `KeyError` on unknown type) as specified in VM-01-003.
