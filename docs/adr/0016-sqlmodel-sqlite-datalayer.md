---
status: accepted
date: 2026-04-13
deciders: ahouseholder
consulted: notes/datalayer-sqlite-design.md, notes/domain-model-separation.md, notes/architecture-ports-and-adapters.md
informed: plan/IMPLEMENTATION_PLAN.md
---

# Replace TinyDB with SQLModel/SQLite DataLayer Adapter

## Context and Problem Statement

The current `TinyDbDataLayer` adapter (`vultron/adapters/driven/datalayer_tinydb.py`)
uses TinyDB, which rewrites the **entire** backing JSON file on every read and write
operation. The I/O cost is therefore O(n) relative to total database size, not query
size. As the test suite grew, this caused the full test run to slow from ~13 seconds
to 15+ minutes (BUG-2026041001).

The fix required patching `TinyDbDataLayer.__init__` in `pytest_configure` to force
`MemoryStorage` globally — infrastructure complexity paid entirely to work around the
backend, not to test application behaviour.

Two architectural options were evaluated: a SQL-native backend (SQLite via SQLModel)
and a document database (MongoDB). A third option — doing nothing and simply patching
around the performance problem — is the status quo.

## Decision Drivers

- Test-suite speed: full run must stay under ~1 minute without a `pytest_configure`
  patch (BUG-2026041001).
- Hex-arch compliance: the chosen adapter must live entirely in
  `vultron/adapters/driven/`; core and wire layers must have zero new imports.
- Test isolation: unit tests that construct a DataLayer directly must get an isolated
  store with no patching or fixtures required.
- Prototype scope: no data migration from existing `mydb.json` files is required
  (IDEA-26040903 — prototype phase, no backward compat).
- Future-proof schema: the storage model should map naturally to a MongoDB document
  collection for a future production upgrade.
- Minimal new infrastructure: avoid adding Docker services or complex tooling on
  the critical path to D5-7-HUMAN.

## Considered Options

- **Option A** — SQLModel/SQLite single-table polymorphic storage (chosen)
- **Option B** — SQLModel/SQLite per-type-table storage
- **Option C** — MongoDB Community Edition in Docker
- **Option D** — Keep TinyDB with MemoryStorage patch (status quo)

## Decision Outcome

Chosen option: **Option A — SQLModel/SQLite single-table polymorphic storage**,
because it delivers row-level I/O, test isolation via `sqlite:///:memory:`, and a
document-oriented schema that maps naturally to MongoDB — all without adding Docker
infrastructure or changing core/wire layer imports.

### Consequences

- Good, because `sqlite:///:memory:` gives automatic per-engine isolation in tests
  with no monkey-patching of application code.
- Good, because row-level SQLite I/O keeps the full test suite under ~1 minute
  regardless of how many records are stored.
- Good, because the single-table `(id_, type_, actor_id, data JSON)` schema mirrors
  a MongoDB collection, making a future backend swap a new adapter + one env-var
  change.
- Good, because `db_record.py`'s `object_to_record` / `record_to_object` helpers
  (vocabulary-registry-aware) are reused unchanged — no new serialization logic.
- Good, because `TECHDEBT-32c` (the `datalayer_tinydb` fallback import in
  `vultron/wire/as2/rehydration.py` that violated CS-05-001) is removed as part
  of the same task (DL-SQLITE-2).
- Neutral, because SQLite is still a single-writer file; concurrent multi-process
  writes are possible but uncommon in the prototype scenario. The file lock is
  acceptable for prototype use.
- Bad, because all existing `mydb.json` data is abandoned (acceptable per
  IDEA-26040903 — prototype phase).
- Bad, because TinyDB's per-table namespace model (actor prefix) is replaced by an
  `actor_id` column; any code that constructs table names directly must be updated.

## Validation

- `uv run pytest --tb=short` passes after each of DL-SQLITE-1 through DL-SQLITE-4,
  with no `pytest_configure` TinyDB monkey-patch in `test/conftest.py`.
- The full test suite completes in under 2 minutes.
- Actor A's `dl.list()` does not return records belonging to Actor B.
- `uv run mypy && uv run pyright` pass with zero errors after DL-SQLITE-4.
- `uv run flake8 vultron/ test/` passes with zero errors after DL-SQLITE-4.

## Pros and Cons of the Options

### Option A — SQLModel/SQLite single-table polymorphic

- Good, because `sqlite:///:memory:` provides automatic isolation per engine in
  tests; no patches needed.
- Good, because row-level I/O; query cost is O(matched rows), not O(total DB size).
- Good, because single table mirrors a MongoDB collection — future migration is
  straightforward.
- Good, because `db_record.py` helpers are reused unchanged.
- Neutral, because adding SQLModel/SQLAlchemy adds ~2 MB of dependency weight.
- Bad, because `type_` queries require a `WHERE type_ = ?` clause instead of a
  per-type table, which is slightly less explicit but well-supported with an index.

### Option B — SQLModel/SQLite per-type-table storage

- Good, because table names match the existing TinyDB table-per-type pattern.
- Bad, because schema migrations require adding new tables for each new domain type.
- Bad, because it does not map to MongoDB's collection model.
- Bad, because IDEA-26040901 (the per-type table consolidation question) identified
  this as the problem to solve; choosing it here would preserve the problem.

### Option C — MongoDB Community Edition in Docker

- Good, because MongoDB is the correct production-grade document store for this
  schema.
- Bad, because it adds Docker infrastructure (MongoDB container, authentication,
  volume mounts) to the critical path before D5-7-HUMAN.
- Bad, because local development requires Docker to run any test.
- Neutral, because this remains the recommended production upgrade path and can be
  added as a new driven adapter after D5-7 without changing the DataLayer port.

### Option D — Keep TinyDB with MemoryStorage patch (status quo)

- Good, because zero implementation cost.
- Bad, because the `pytest_configure` patch is accidental complexity: it patches
  application code for an infrastructure reason, making the test setup fragile.
- Bad, because TinyDB O(n) writes will continue to slow the suite as coverage grows.
- Bad, because TECHDEBT-32c remains.

## More Information

- `notes/datalayer-sqlite-design.md` — canonical design note for the SQLite adapter:
  schema, actor scoping, `db_record.py` reuse, test isolation, URL patterns,
  migration notes.
- `notes/domain-model-separation.md` — "DataLayer as a Port" and "Per-Actor
  DataLayer Isolation Options" sections (historical context; superseded by this ADR).
- `plan/IMPLEMENTATION_PLAN.md` — Phase PRIORITY-325, tasks DL-SQLITE-ADR through
  DL-SQLITE-5.
- `vultron/adapters/driven/db_record.py` — `object_to_record` / `record_to_object`
  helpers that MUST be reused by the new adapter for vocabulary-registry-aware
  deserialization.
- `vultron/core/ports/datalayer.py` — `DataLayer` Protocol (port); unchanged by
  this decision.
- ADR-0012 (`0012-per-actor-datalayer-isolation.md`) — prior decision on per-actor
  isolation; the SQLite `actor_id` column is structurally equivalent to the TinyDB
  namespace-prefix (Option B) chosen in that ADR.
