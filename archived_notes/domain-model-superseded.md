# Superseded: DataLayer Design (Pre-Priority-325)

> These sections were removed from `notes/domain-model-separation.md` in
> April 2026, after Priority 325 (SQLModel/SQLite migration) and Priority 340
> (wire-domain translation boundary) were completed.
> They are retained here for historical reference only.

---

## DataLayer as a Port, TinyDB as a Driven Adapter ~~HISTORICAL~~

> **Status**: TinyDB was replaced by SQLModel/SQLite in Priority 325.
> The port/adapter split described here is complete and correct; only the
> concrete adapter changed. See `notes/datalayer-sqlite-design.md` (in
> `archived_notes/` as of Priority 325 completion).

Independently of per-actor isolation, the `DataLayer` interface is treated as
a **port** in the hexagonal architecture sense, and the `TinyDbDataLayer`
implementation as a **driven adapter** that satisfies the port.

This distinction matters even now, before per-actor isolation is implemented:

- The port (Protocol interface) defines what the domain needs from persistence.
- The adapter (TinyDB) provides a concrete implementation behind that interface.
- A future MongoDB adapter would implement the same Protocol without requiring
  core domain changes.

**Current state (P65-1 complete)**: The `DataLayer` Protocol is defined in
`vultron/core/ports/datalayer.py`. The old location
(`vultron/api/v2/datalayer/abc.py`) is a backward-compat re-export shim. All
core BT nodes import `DataLayer` from `core/ports/`. Handlers receive the
`DataLayer` via dependency injection (achieved in ARCH-1.4).

**Remaining step (P70)**: Relocate the `TinyDbDataLayer` implementation and
`get_datalayer()` factory from `vultron/api/v2/datalayer/` to
`vultron/adapters/driven/datalayer_tinydb.py` (or equivalent) when P60-3
(adapters package stub) is complete.

**Design Decision**: The DataLayer relocation into the adapter layer SHOULD
be planned together with PRIORITY 100 (actor independence) and the potential
MongoDB switch. See the per-actor isolation options below.

---

## Per-Actor DataLayer Isolation Options ~~SUPERSEDED~~

> **Superseded by Priority 325 (DL-SQLITE-*).**
> The analysis below was written when TinyDB was still the backend and
> the actor-isolation question was open. Priority 325 resolves both: the
> SQLModel/SQLite adapter uses a single file with an `actor_id` column index
> (analogous to "Option B" below) and the MongoDB recommendation has been
> set aside in favour of SQLite for prototype-phase work.
> See `notes/datalayer-sqlite-design.md` for the current design.

All actors currently share a singleton `TinyDbDataLayer` backed by a single
`plan/mydb.json` file. This violates `specs/case-management.yaml` CM-01-001
(actor isolation) even though demo scripts manually sequence activities to
simulate isolation.

Before implementing PRIORITY 100 (actor independence), a design decision is
needed. Three options:

**Option A — One file per actor**
Each actor gets its own TinyDB file (e.g., `{actor_id}.json`). Simple to
reason about, but creates many files and complicates the DataLayer reset
endpoint used by demo scripts.

**Option B — Namespace prefix per actor (one file)**
One TinyDB file with a separate table per `actor_id`. Keeps a single file;
partitions data cleanly by actor. **This was the recommended TinyDB option.**

**Rationale for Option B**: In a production database (e.g., MongoDB), you
would naturally use a separate collection or namespace per actor. Option B
mirrors that pattern at the TinyDB level — making migration to a robust
backing store straightforward. It also supports the multi-tenant scenario
where a vulnerability disclosure provider connects multiple actor containers
to a single backing store; and the vendor scenario where all actor containers
share a vendor-specific backing store. Option B is the path of least
resistance to production readiness.

**Option C — In-memory DataLayer per actor (no persistence)**
A dict-backed DataLayer scoped per actor. Good for tests; insufficient for
production or Docker demos where state must survive restarts.

### Production Path ~~SUPERSEDED~~

> **Superseded by Priority 325.**
> The MongoDB recommendation below pre-dates the BUG-2026041001 root-cause
> analysis. After measuring that TinyDB's O(n) I/O cost was the dominant test
> bottleneck, the decision was made to replace TinyDB with a SQLModel/SQLite
> adapter (single-table polymorphic) rather than jump to MongoDB. SQLite
> satisfies the prototype-phase requirements with no additional infrastructure.
> MongoDB remains a viable future upgrade path if sharding or horizontal scale
> becomes a requirement.

When implementing PRIORITY 100 (actor independence), the recommended
production-grade approach is to **replace TinyDB with MongoDB Community
Edition** running in Docker. This is separate from the namespace prefix
decision for the TinyDB prototype but should be done in tandem with
actor independence work, for two reasons:

1. **Demonstration credibility**: Showing each actor running in its own
   container with its own MongoDB-backed DataLayer instance is a much
   stronger demonstration of true actor independence than a shared TinyDB
   file with namespace prefixes.
2. **Docker Compose readiness**: Standardized MongoDB community images
   and Docker Compose dependency patterns make multi-actor demos
   straightforward to configure. This is significantly easier than
   continuing to extend TinyDB for multi-actor scenarios.

**Implementation note**: Whichever backing store is chosen, the `BackgroundTasks`
inbox handler MUST resolve the correct per-actor DataLayer instance from the
`actor_id` route parameter. The `get_datalayer` FastAPI dependency MUST accept
an `actor_id` argument and return an isolated instance. Triggerable behavior
endpoints (PRIORITY 30) share the same dependency injection mechanism.
