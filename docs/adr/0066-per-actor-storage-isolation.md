---
status: accepted
date: 2026-08-17
deciders: ahouseholder
consulted: notes/datalayer-design.md, notes/actor-knowledge-model.md, vultron/core/ports/AGENTS.md, docs/adr/0012-per-actor-datalayer-isolation.md
informed: specs/datalayer.yaml, specs/architecture.yaml, specs/case-management.yaml
---

# Give Each Actor Its Own Store; Delete the Unscoped DataLayer

## Context and Problem Statement

`specs/case-management.yaml` CM-01-001 requires that each actor have an
isolated protocol state domain. The SQLite DataLayer does not provide that.
It treats one database file as a multi-tenant store, using `actor_id` as a
**filter column** over a **globally unique** primary key. Reads are
partitioned; writes are not.

Issue #2238 is the visible consequence. `VultronObjectRecord.id_` is the sole
primary key, so two actors sharing a store cannot both hold a replica of the
same object ID:

- `crud.create()` checked existence with a bare primary-key `get`, so the
  second actor's `create()` raised `ValueError`. Both case-bootstrap sites
  swallowed that as a benign concurrent insert, leaving that actor with no
  replica row it could read.
- `crud.save()` had the same unscoped lookup and *no* error. One actor's
  `save()` silently overwrote another actor's row contents while leaving the
  row owned by the original actor — so the writer could not read its own
  write back, and the original owner read the writer's data.

Neither case is hypothetical. A single container hosts an actor plus the
CaseActors it self-hosts (CP-08-003, pending #1700), and single-server demo
mode runs every actor against one configured store.

The deeper problem is that isolation was a property of *every individual
query* rather than of the storage layout. `SqliteDataLayer._scoped()` had to be
applied by hand, and any path that forgot it — every write path did — reopened
the leak. The `ARCH-13` requirement group and the `ActorScopedDataLayer`
protocol refinement exist only to police that hazard, and
`notes/datalayer-design.md` carries two further pitfalls
(`outbox_list()` requires `clone_for_actor`; the dual-DataLayer isolation
guard) that are symptoms of the same root cause.

The unscoped mode is also load-bearing in ways that contradict the invariant.
`deps.py` states it plainly: *"Operational data (actors, offers, reports,
cases) is stored in the shared DataLayer."*

There is a second leak, in *execution identity* rather than storage layout.
`BTBridge.setup_tree` puts `datalayer` and `actor_id` on the blackboard as two
independent facts, so they can disagree. Under per-actor storage they are one
fact: a store is always some actor's own, so the executing actor's identity
*determines* which store the tree operates on.

The delegated-emit pattern is where this bites. A trigger emitting on the
CaseActor's behalf runs with `actor_id` set to the CaseActor (CM-24-001) while
the injected DataLayer belongs to the *requesting* actor. So the activity is
created in the requester's store and queued in the CaseActor's outbox: the
CaseActor never delivers it, and its outbox names an activity its own store does
not hold (PCR-08-007, CM-24-004).

An outbox call-site survey missed this, and it is worth recording why. The four
`record_outbox_item` sites traced below name the actor in an *argument*, and all
four are genuinely self-directed. This seam is different: the mismatch arrives
through the blackboard, so no call site reads as cross-actor. "Every outbox call
site passes the executing actor's own id" is true of the traced sites and false
at the trigger seam.

## Decision Drivers

- CM-01-001: each actor MUST have an isolated protocol state domain.
- The invariant to enforce is absolute: **one actor's writes must never affect
  what another actor could read.** "Ever" rules out guarantees that depend on
  every query being written correctly.
- Core must stay agnostic to the storage layout — a robust database, a folder
  of JSON files per actor, or anything between (the DataLayer port is the
  contract; see `notes/datalayer-design.md` § "Key principle").
- The Actor Knowledge Model: an actor's knowledge of the world is bounded by
  what it has received. An actor's view of its peers is *that actor's own
  data*, not node-global data.
- Isolation guarantees that rely on discipline have already failed here once
  (#2232 produced two ratchets for one problem).

## Considered Options

- **Option A** — One store per actor; `actor_id` mandatory; no unscoped mode.
- **Option B** — One store, composite primary key `(id_, actor_id)`, scoping
  enforced in every query.
- **Option C** — Per-actor schema or `ATTACH`-ed database inside one file.

## Decision Outcome

Chosen option: **Option A — one store per actor, `actor_id` mandatory**.

Only Option A makes the invariant structural. With a separate engine per
actor there is no `WHERE` clause to omit, no `actor_id` column to mis-populate,
and no query that *could* return another actor's row. Options B and C both
leave cross-actor access expressible in SQL, so they convert the invariant into
a code-review obligation — which is the failure mode being removed.

Concretely:

- The configured `db_url` becomes a template. `sqlite:////app/data/mydb.sqlite`
  yields `mydb-<slug>.sqlite` per actor; `sqlite:///:memory:` yields one
  private in-memory engine per actor.
- `SqliteDataLayer` **requires** an `actor_id`. `_scoped()`, the `actor_id`
  column, `get_shared_dl()`, and `get_datalayer()`-with-no-actor are deleted.
- The URL path segment is resolved to a canonical actor URI by **computation**,
  not lookup: `VULTRON_SERVER__BASE_URL + "actors/" + segment`. This removes
  the last genuine need for a cross-actor scan. It holds for runtime-created
  CaseActors, whose IDs are already
  `{case_actor_service_url}/actors/case-actor-{slug}`.
- `record_outbox_item(actor_id, …)` and `outbox_list_for_actor(actor_id)`
  collapse into `outbox_append()` / `outbox_list()` at **all** call sites. The
  explicit-actor form existed because the injected DataLayer might be unscoped,
  not because any site wrote to a genuinely foreign queue.

  Four sites make that non-obvious, because they name the actor via a variable
  (`case_actor_id`, `sender_actor_id`, `enqueue_actor_id`) rather than
  `self.actor_id`. Traced through, all four are self-directed: two author as the
  executing actor or merely re-queue an activity authored earlier
  (`case/nodes/participant/common.py`, `fastapi/pending_retry.py`), and two —
  `case/update_support.py` and `sync/nodes/replay.py` — emit activities whose
  `actor` is the CaseActor while *running as* the CaseActor.

  Those last two conflate three separate ideas that CM-24 keeps apart on the
  wire and then muddles in storage: the activity's `actor` (CM-24-001), its
  `attributed_to` (CM-24-002), and **whose store this is**. The first two are
  wire authorship; the third is infrastructure. Spelling the first and third
  with one variable made a local write look like a foreign one.

  Resolution: **gate on the role, not on an identity comparison.** A CaseActor-
  authored emit MUST sit inside a role-gated composite that verifies the
  executing actor holds `CVDRole.CASE_MANAGER` for the case
  (`CheckIsCaseManagerNode`), exactly as CLP-09 already requires for canonical
  ledger commits — appending to the log and announcing the append are one
  privilege. Code MUST NOT instead compare `actor_id` against a computed
  `case_actor_id`; the authority is a role held in the case, and the holder may
  be any Actor type. Once gated, the executing actor *is* the case manager, so
  `outbox_append()` is correct by construction.

  This also fixes a latent defect the isolation exposes. Those sites `create()`
  the activity in the executing actor's store and enqueue its id under the
  named actor. A shared pool made that work by accident; with per-actor stores
  the reader would find no activity for the id. Gating makes both halves land in
  one store.

  Ungated, this is identity spoofing — any actor reaching the helper could emit
  an `Announce` authored as the CaseActor to every participant — which
  `AGENTS.md` already forbids for received-side use cases.
- `ActorScopedDataLayer` merges back into `DataLayer`: with no unscoped mode,
  the distinction has no referent.
- Peer actor records live in the address book of each hosted actor that needs
  them. This is safe because delivery derives a recipient's inbox URL from its
  URI alone (`http_delivery.py`: `recipient_id.rstrip("/") + "/inbox/"`) and
  never reads the peer's stored record.
- `GET /actors/` returns only the actors this node hosts. A peer is not
  something the node hosts; it is an address some hosted actor happens to know.

- **A BT's store follows its executing actor**, reconciled once in `BTBridge`
  rather than at each BT invocation (`_store_for_actor`). Chosen over fixing only
  the trigger seam for the same reason isolation must not depend on every query
  remembering a filter: correctness must not depend on every BT invocation
  remembering to re-scope. Normative as BT-05-005.

  The stronger choice is not free, and the cost was measured rather than
  estimated. Fixing only the trigger seam left 139 failing tests across 10 extra
  files; forcing the store to follow the executing actor everywhere took the
  suite to 622 failures across 123 files. The maintainer took the structural fix
  with that number in hand.

  A related invariant falls out and is normative as BT-05-006: where a tree is
  gated on a role, the role holder, the receiving actor and the store owner must
  be one actor. Letting any two drift makes the gate evaluate against an actor
  holding no role, which returns SUCCESS-by-skip and writes nothing. Nothing
  raises, which is what makes it worth a MUST.
- **Cross-actor access must be named.** `clone_for_actor` is the only route to
  another actor's store, and `CasePersistence` declares it, so a fan-out is
  explicit in the type as well as in the code rather than something a forgotten
  filter grants.

This supersedes the "DataLayer isolation strategy" half of ADR-0012, which
chose *Option B — namespace prefix per actor in one file*. ADR-0012's other
three decisions (DI-1 closure lambda, IO-A queues in the DataLayer, OX-B
deferral) are unaffected. ADR-0012's own reasoning for rejecting one-file-per-actor
was that it "creates many files and complicates the DataLayer reset endpoint"
and "diverges from the MongoDB collection model" — a prototype-convenience
argument that does not survive being weighed against CM-01-001.

### Consequences

- Good, because cross-actor access becomes impossible rather than incorrect.
  A future contributor cannot reintroduce the leak by forgetting a filter.
- Good, because it *deletes* guard rails instead of adding them: ARCH-13-001,
  ARCH-13-002 and ARCH-13-004 become vacuous, `ActorScopedDataLayer`
  disappears, and two long-standing DataLayer test pitfalls stop existing.
- Good, because per-container behaviour now matches the deployed topology,
  where each container already has its own volume.
- Good, because it makes the demo's per-container peer seeding
  protocol-correct rather than a shared pool that merely looks partitioned.
- Bad, because any legitimately cross-actor read must now fan out over stores
  explicitly. `GET /actors/` narrows, and node-wide admin views must be
  assembled rather than queried.
- Bad, because it is a large, wide change: the adapter, both persistence
  ports, the FastAPI actor routes, demo seeding for all nine scenarios, and a
  large number of test fixtures.
- Neutral, because a node hosting several actors now holds several files.
  This is a prototype-scale cost and mirrors the intended per-actor
  collection/database model of a production backend.

## Validation

- The regression tests in `test/adapters/driven/test_datalayer_isolation.py`
  assert the invariant directly: two actors sharing one configured store each
  create and read back their own replica of the same object ID, and one
  actor's write cannot change what another reads.
- `SqliteDataLayer` cannot be constructed without an `actor_id`, so the
  unscoped mode is unreachable rather than merely discouraged.
- `test/core/behaviors/test_bridge.py` asserts the Leak 2 invariant directly: the
  blackboard's `datalayer.actor_id` equals its `actor_id`, and — as the
  complement, so the reconciliation cannot be satisfied by cloning
  unconditionally — an injected store that already belongs to the executing actor
  is passed through un-cloned.

## Pros and Cons of the Options

### Option A — One store per actor, `actor_id` mandatory

- Good, because isolation is a property of the layout, not of each query.
- Good, because it removes the `ARCH-13` guard rails and the
  `ActorScopedDataLayer` refinement rather than maintaining them.
- Good, because it matches the Actor Knowledge Model: each actor's store holds
  exactly that actor's knowledge.
- Bad, because cross-actor reads require explicit fan-out.
- Bad, because it is the largest of the three diffs.

### Option B — One store, composite primary key `(id_, actor_id)`

- Good, because it is the smallest change that lets two actors each hold a
  replica.
- Good, because cross-store admin views remain a single query.
- Bad, because isolation still depends on every query applying the scope; one
  missing filter silently reopens the leak.
- Bad, because it requires `actor_id` to become non-nullable with a sentinel
  for the unscoped writes that exist today, and keeps the unscoped concept
  alive.

### Option C — Per-actor schema or `ATTACH`-ed database in one file

- Good, because it is structural like Option A while keeping one file.
- Bad, because dynamic table naming or attached-schema routing is the least
  idiomatic option for SQLModel and adds real SQLAlchemy complexity.
- Bad, because it retains a single file as a shared failure and contention
  domain without buying back the simplicity that motivated it.

## More Information

- Issue #2238 — the reported defect and its acceptance criteria.
- ADR-0012 — supersedes its DataLayer isolation strategy decision only.
- ADR-0042 — all inter-actor communication is over HTTP, which is why no
  cross-actor store access is needed for delivery.
- `notes/datalayer-design.md` — DataLayer port contract and the pitfalls this
  decision retires.
- `notes/actor-knowledge-model.md` — why peer records belong to the actor.
- CP-08-003 / #1700 — the vendor self-hosting its CaseActors, one of the two
  topologies that exposed the defect.

Generated spec requirements: `specs/datalayer.yaml` DL-07-001 through DL-07-008
(per-actor store isolation); `specs/behavior-tree-integration.yaml` BT-05-005 (a
BT's store is its executing actor's) and BT-05-006 (role holder, receiving actor
and store owner are one actor); `specs/em-behavior.yaml` EMB-18 (the teardown
announcement's author and recipients, unspecified until this change exposed the
gap).

Retires `specs/architecture.yaml` ARCH-13-001, ARCH-13-002, ARCH-13-004 and
ARCH-13-005 as vacuous. ARCH-13-005 was not in the original plan: it asks for the
`ActorScopedDataLayer` Protocol, which this decision deletes, so it was
unimplementable rather than merely redundant. ARCH-13-003 is *amended, not
retired* — its substance (a store is opened under the actor's canonical URI, never
a short id) survives and is load-bearing, but its wording named
`ActorScopedDataLayer` and `record_outbox_item`.

Amends DL-04-002 and DL-04-004 for the collapsed outbox methods and the
`actor_id`/`clone_for_actor` additions to `CasePersistence`; CM-24-004 to require
the role gate instead of the `self._actor_id` convention; and BT-17-006, which
required `actor_id=request.receiving_actor_id` outright and so forbade the
store-owner fallback it should require.
