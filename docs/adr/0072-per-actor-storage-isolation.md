---
status: accepted
date: 2026-08-17
deciders: ahouseholder
consulted: notes/datalayer-design.md, notes/actor-knowledge-model.md, vultron/core/ports/AGENTS.md, docs/adr/0012-per-actor-datalayer-isolation.md, docs/adr/0041-caseactor-authoritative-case-initialization.md, docs/adr/0058-causal-gating-in-demo-scenarios.md
informed: specs/datalayer.yaml, specs/architecture.yaml, specs/case-management.yaml, specs/case-proposal.yaml, specs/behavior-tree-integration.yaml, specs/em-behavior.yaml, specs/inbox-endpoint.yaml, specs/participant-case-replica.yaml, specs/idempotency.yaml, specs/case-bootstrap-trust.yaml
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

There is a third leak, and it is the one this decision originally failed to
name. Per-actor storage makes cross-actor *access* impossible; it does nothing
about cross-actor *expectation*. Code can still be written as though a
co-located actor's knowledge were its own, and nothing in the layout says
otherwise — the read simply comes back empty.

Issue #2548 is that leak in the field. A single container hosts the report
receiver and the CaseActor it self-hosts. Under ADR-0041 the receiver does not
create the case: it submits a `CaseProposal`, and the CaseActor creates the case
in **its own** store and replicates it back as `Create(VulnerabilityCase)`. The
receiver's `validate-report` tree ran before that replica arrived, found no case
— correctly — and advanced anyway, writing the report-phase `RM.VALID` latch
while the case-scoped `CaseParticipant` stayed at `RECEIVED`. Because the guard
that decides whether to run the transition reads that same latch, the two halves
could never reconverge. The case state had split across two stores and the split
was permanent.

Nothing in this ADR licensed that, but nothing forbade it either. The invariant
as originally stated is about writes ("one actor's writes must never affect what
another actor could read"); the missing half is about reads, and it has to be
stated as a property of the *protocol* rather than of the storage layout,
because the temptation it removes is a deployment-shaped one.

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
- **Co-location is an implementation choice the protocol must remain
  indifferent to.** One host or a hundred, actors exchange information only by
  protocol message. No back-end cheats: no direct writes into another actor's
  store, no out-of-band signalling between actors that happen to share a
  process. A guarantee that holds only when the topology cooperates is not a
  protocol guarantee.
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

  **The store is not the only thing that holds a store**, and reconciling it
  alone leaves the other half looking correct. Normative as DL-07-009: every
  store reference reachable from an actor-scoped execution follows that actor,
  not just the one on the blackboard. The driven adapters injected into a BT —
  `TriggerActivityPort`, `SyncActivityPort` — keep the DataLayer they were
  constructed with, and the adapter is what *persists* the outbound activity. So
  BT-05-005 alone fixed the queue and left the activity behind: a delegated emit
  created the `Invite` in the requesting actor's store while the node appended
  its id to the executing actor's outbox. Delivery then found the queue entry,
  could not read the activity, logged "not found in DataLayer", and skipped — the
  invitee was never told it had been invited, and no error surfaced anywhere.

  Rebinding is **opt-in**: a component declares a named way to be rebound
  (`for_store`) or holds no store at all. Opt-in rather than automatic because a
  stateless collaborator must not be replaced behind its caller's back, and the
  declaration is read off the *type* rather than the instance because a test
  double answers any attribute — an instance-level probe would silently rebind
  every mock in the suite.
- **Cross-actor access must be named.** `clone_for_actor` is the only route to
  another actor's store, and `CasePersistence` declares it, so a fan-out is
  explicit in the type as well as in the code rather than something a forgotten
  filter grants.

- **The protocol is indifferent to co-location, and code must be too.**
  Normative as PCR-01-003. Actors exchange information *only* through protocol
  messages — never a direct read or write into another actor's store, never
  out-of-band communication between actors that happen to share a host. The
  operative consequence for the case lifecycle: an actor that has asked a
  CaseActor to create a case MUST treat that case as absent from its own
  knowledge until the CaseActor's `Create(VulnerabilityCase)` has been delivered
  to it. Co-location does not make the case visible sooner. Absence of the
  replica is a legitimate, transient state — the correct response is to fail the
  case-scoped work and retry, never to proceed as though the case were there
  (ARCH-15-001).

  This is not merely about where bytes live, so it is worth being exact about
  who holds what. The CaseActor **creates** the case and holds
  `CVDRole.CASE_MANAGER`: what it owns is *write privilege on the case ledger*.
  The actor whose `CaseProposal` caused the case to exist — the report receiver,
  whatever other roles it also holds — holds `CVDRole.CASE_OWNER`. That role is
  **never delegated to the CaseActor**. "The case-actor's store holds the
  canonical case" and "the case-actor owns the case" are different claims, and
  only the first is true. CBT-01-003 is amended accordingly: it previously said
  "case creator/owner", which under ADR-0041 names two different actors.

  Stated flatly, because #2548 showed the question had no written answer: **when a
  container hosts both a primary actor and a co-located CaseActor, the case lives
  in the CaseActor's store, and the primary actor holds a replica it receives by
  protocol message.** There is no write-through from the CaseActor into the
  primary actor's store, and no shared per-container store. The two rejected
  alternatives fail for the same reason:

  - *The primary actor owns the case and the CaseActor writes through to it via
    `clone_for_actor`* — this is a back-end cheat. It works only while the two
    actors are co-located, so it is not a protocol guarantee, and it makes the
    CaseActor's authority over the ledger depend on the deployment topology.
  - *A container has one store shared by the roles it wears; isolation applies
    only across containers* — this contradicts CM-01-001 directly and reinstates
    the multi-tenant store this decision exists to remove. It would also make a
    self-hosted CaseActor structurally different from a remotely-hosted one,
    which is exactly the indifference PCR-01-003 requires.

  The consequence a reader must carry away is a timing one, not a location one:
  the replica arrives *later than the case exists*, so any case-scoped work in the
  primary actor is gated on the replica having actually landed in its own store.
  That gate is the fix; it is not an optimisation to be skipped when the actors
  happen to share a host.

- **The latch is written last.** Normative as ID-04-005. When a transition has
  more than one half and one half doubles as the evidence a later guard reads,
  that half MUST be written only after the others have succeeded. Writing it
  first turns a recoverable "not yet" into a permanent "already done": the guard
  suppresses every retry, and nothing raises. This is the mechanism by which the
  #2548 store split became irreversible rather than merely late, and it belongs
  here because per-actor isolation is what makes "not yet" a routine state
  instead of a rare one.

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
  ARCH-13-002, ARCH-13-004 and ARCH-13-005 become vacuous,
  `ActorScopedDataLayer` disappears, and two long-standing DataLayer test
  pitfalls stop existing. (ARCH-13-003 survives, amended — see Compliance.)
- Good, because per-container behaviour now matches the deployed topology,
  where each container already has its own volume.
- Good, because it makes the demo's per-container seeding protocol-correct
  rather than a shared pool that merely looks partitioned. *Peer* seeding is
  not yet correct: a peer is registered through `POST /actors/`, which mints a
  local store for a foreign-authority id, so a node still claims to host
  processes it does not serve. Decision 5 says what a peer *is*; issue #2549
  tracks making the seeding path agree.
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
- The Leak 3 invariant is asserted where the split appeared. In
  `test/core/use_cases/received/test_ack_validate_report_received.py`,
  `test_full_flow_no_rm_valid_before_case_replica_arrives` drives the real
  submit → validate flow *without* delivering the replica and asserts that no
  `RM.VALID` record is written at all; the companion test delivers the replica
  first and asserts both halves advance in lockstep. In
  `test/demo/test_workflow_rm_triage.py`,
  `test_validate_gated_on_local_case_replica` asserts the causal ordering
  (replica present *therefore* validate) rather than mere sequence, so the gate
  cannot regress to a post-hoc presence check — the shape ADR-0058 rejects and
  the shape the old code had.
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
- Issue #2548 — the case-state split that exposed Leak 3; fixed on the same
  branch, because it is a problem this change made visible rather than one it
  found.
- ADR-0041 — CaseActor-authoritative case initialization; why the report
  receiver never holds the case until the replica is delivered.
- ADR-0058 — gate on causal preconditions, not temporal order; why the replica
  wait is a gate and the old post-hoc case check was not.
- ADR-0012 — supersedes its DataLayer isolation strategy decision only.
- ADR-0042 — all inter-actor communication is over HTTP, which is why no
  cross-actor store access is needed for delivery.
- `notes/datalayer-design.md` — DataLayer port contract and the pitfalls this
  decision retires.
- `notes/actor-knowledge-model.md` — why peer records belong to the actor.
- CP-08-003 / #1700 — the vendor self-hosting its CaseActors, one of the two
  topologies that exposed the defect.

Generated spec requirements: `specs/datalayer.yaml` DL-07-001 through DL-07-008
(per-actor store isolation) and DL-08-001/DL-08-002 (storage must keep a
reference inline where the model requires the object to be carried);
`specs/behavior-tree-integration.yaml` BT-05-005 (a BT's store is its executing
actor's) and BT-05-006 (role holder, receiving actor and store owner are one
actor); `specs/em-behavior.yaml` EMB-19 (the teardown announcement's author and
recipients, unspecified until this change exposed the gap);
`specs/participant-case-replica.yaml` PCR-01-003 (co-location grants no
visibility; actors exchange information only by protocol message) and
`specs/idempotency.yaml` ID-04-005 (a guard record is written last, never
first) — both from #2548.

DL-08 is here because isolation is what exposed it (#2482). A `CaseProposal`
must carry its report inline (CP-01-004), but persistence dehydrated the
reference like any other, and only the *first* level of an inbound activity's
nesting is given a record — so the report collapsed to an id nothing could
resolve. A shared store had hidden it: the vendor stored the report when it
received the Offer, and that row was visible to the CaseActor too. With per-actor
stores the CaseActor has only what it is sent.

Retires `specs/architecture.yaml` ARCH-13-001, ARCH-13-002, ARCH-13-004 and
ARCH-13-005 as vacuous. ARCH-13-005 was not in the original plan: it asks for the
`ActorScopedDataLayer` Protocol, which this decision deletes, so it was
unimplementable rather than merely redundant. ARCH-13-003 is *amended, not
retired* — its substance (a store is opened under the actor's canonical URI, never
a short id) survives and is load-bearing, but its wording named
`ActorScopedDataLayer` and `record_outbox_item`.

Amends DL-04-002 and DL-04-004 for the collapsed outbox methods and the
`actor_id`/`clone_for_actor` additions to `CasePersistence`; CM-24-004 to require
the role gate instead of the `self._actor_id` convention; BT-17-006, which
required `actor_id=request.receiving_actor_id` outright and so forbade the
store-owner fallback it should require; and CBT-01-003, which said "case
creator/owner" as though one actor, where ADR-0041 makes the CaseActor the
creator (`CVDRole.CASE_MANAGER`) and the proposal's submitter the owner
(`CVDRole.CASE_OWNER`).
