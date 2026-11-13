---
title: "DataLayer Design: Architecture and Migration Notes"
status: active
kind: guidance
tags: [datalayer, ports, persistence, architecture, hexagonal]
description: >
  Rules for the DataLayer port contract, CasePersistence narrowing, the
  write/read shape boundary, activity read-back, the received archive as the
  sealed body, received-activity keying, received-artifact snapshots, per-actor
  stores, shared-record writes, multi-call transactions and their read seam,
  and stored-shape changes. Operating rules live in vultron/core/ports/AGENTS.md.
related_specs:
  - specs/datalayer.yaml
  - specs/architecture.yaml (ARCH-12-003, ARCH-12-006, ARCH-23-003, ARCH-23-005)
  - specs/embargo-policy.yaml (EP-02-004)
  - specs/message-validation.yaml (MV-11-004, MV-11-012)
  - specs/case-management.yaml (CM-11-017)
  - specs/outbox.yaml (OX-06-002)
  - specs/inbox-endpoint.yaml (IE-10-001)
  - specs/vocabulary-model.yaml (VM-08-002)
  - specs/case-ledger-processing.yaml (CLP-07-015)
related_notes:
  - notes/architecture-hexagonal.md
  - notes/case-ledger-authority.md
  - notes/activitystreams-semantics.md
  - notes/wire-core-boundary.md
  - notes/testing-pitfalls.md
  - notes/flaky-tests.md
  - notes/vocabulary-registry.md
  - notes/case-bootstrap-trust.md
  - notes/case-proposal.md
  - notes/wire-artifact-immutability.md
  - notes/triggerable-behaviors.md
relevant_packages:
  - vultron/core/ports
  - vultron/core/behaviors
  - vultron/adapters/driven
  - vultron/wire/as2/vocab
---

# DataLayer Design: Architecture and Migration Notes

Operating rules summary: `vultron/core/ports/AGENTS.md`.
Specs: `specs/datalayer.yaml`.

`dl.read()` returns core objects, never wire objects (ADR-0034), and core
reads a received activity's facts only from the read-only view its archive loads
(ADR-0149, DL-06-001; see "Activity Read-Back" below).

## DataLayer vs. CasePersistence

The repository distinguishes between two layers of persistence contract:

| Port | Intended callers | Purpose |
| --- | --- | --- |
| `DataLayer` | adapters, routers, infrastructure code | Full adapter-level contract, including persistence, queue operations, health/admin helpers, and diagnostics |
| `CasePersistence` | core use cases and BT nodes | Narrow core-facing persistence/query contract |
| `CaseOutboxPersistence` | the small subset of core code that also enqueues outbound activities | `CasePersistence` plus outbound enqueue methods only |

`CasePersistence` (`vultron/core/ports/case_persistence.py`) is intentionally
narrower than `DataLayer`. Add a method to it only when the method preserves the
core-facing persistence/query boundary; queue methods, health checks, admin
helpers, diagnostics, and low-level storage primitives stay on `DataLayer`.
In core, use `read_case()` for a `VulnerabilityCase` (typed, no `isinstance`
narrowing), `read()` for other single objects, `list_objects()` for typed
collections, and a dedicated typed helper when a generic query would expose raw
persistence details.

## CaseOutboxPersistence Marks Code That Sends

Declare `CaseOutboxPersistence` only where core code queues outbound activities:
the port adds `outbox_append` and `outbox_list` to `CasePersistence` (DL-04-004),
so the type shows which code sends. A received use case declares it when its
tree's effects stage emits, which is the received-tree order by design
(ADR-0111), not a defect to split out.

## Write Path Stores Verbatim; the Boundary Is `extra="forbid"`

The shape guard lives on the *type*, not the write path (ARCH-12-003, ADR-0082).
`CoreObject` sets `extra="forbid"`, so handing a wire-shaped payload to a core
type raises a pydantic `ValidationError` instead of silently dropping every
snake_case-only key. A wire-shaped row in a core-typed slot is not cosmetic:
core `ParticipantStatus` nests `rm: RmDimension`, and a wire row written before
issue #4377 carried a flat `rm_state`, which now fails validation rather than
leaving `status.rm.state` at its default.

- **Writes store verbatim.** `Record.from_obj()` and `_storable_to_record()` do
  not project; a row is persisted in the shape it arrived in. Do not add a
  write-side normalisation gate back.
- **Reads project.** `ValidationError` is the shape-mismatch signal that drives
  the read-side fallback in
  `vultron/adapters/driven/datalayer_sqlite/hydration/row_types.py`
  (`project_wire_row_to_core`), so a wire-shaped row still reads back as core.
  When that projection also fails, `dl.read()` logs a WARNING and returns the
  **wire** object (see "A DataLayer Fallback Is a Smell" below).

Two caveats before touching this path:

- `extra="forbid"` rejects *unknown* keys only. `rmState` on `ParticipantStatus`
  is a declared `AliasChoices` spelling, so it is *interpreted*, not rejected.
  The flat `rm_state` is not declared, so it is rejected (SDO-03-003, #4377).
- Persisted rows use wire-facing identity keys (`id`, `type`, `@context`):
  `Record.from_obj()` applies `_rekey_wire_identity()` after `_dehydrate_data()`
  (ARCH-23-005).

## Activity Read-Back: Semantic Content vs. Envelope Reconstitution (ADR-0035, DL-06)

An AS2 Activity is an **envelope** that carries a core fact between isolated
actors, not a domain object. `dl.read(activity_id)` in `vultron/core/` is the
symptom of a domain fact with no home in core (ARCH-09-001). Keep the three needs
it conflates apart:

| Need | Source of truth | Rule |
|---|---|---|
| **Semantic content** — what a message *means* | **Core state**, or the archive's read-only view | Core reads a received activity's facts only from the view its archive loads, never from a wire row (DL-06-001, DL-06-002, ADR-0149). |
| **Correlation** — which prior message this answers | **Core-entity relationship** | Resolve through a domain relationship, not a wire re-read (DL-06-003). |
| **Envelope reconstitution** — verbatim original in a reply's `object_` | **The archived sealed body** | Read only via a wire/adapter seam that parses the sealed body and embeds it verbatim; never a re-dump of the view (DL-06-004, ADR-0149). |

The extractor (the single interpretation site, ARCH-03-001) records each domain
fact as core state at interpretation time — a transition on an existing core
entity or a purpose-built core record (for example `VultronOfferRecord`, or an
index on `VulnerabilityCase` such as `pending_embargo_proposal_index`). This is
**not** a 1:1 clone of the AS2 Activity into core — a generic event mirroring AS2
is the anti-pattern ADR-0035 rejects; model only the domain fact, in domain
vocabulary, capturing only what handlers use.

**Why the envelope seam is legitimate.** Activity ids are non-regenerable random
`urn:uuid:` values, and the Actor Knowledge Model requires a reply to embed the
*full inline original* activity, so a reply's `object_` cannot be re-projected
from core state. The seam lives in the adapter
(`vultron/adapters/received_archive.py`, used by
`vultron/adapters/driven/trigger_activity_adapter/`), which parses the stored body
and hands it to the factory, whose `as_answered` embeds it as received. As a core
site migrates, remove its Activity type from the DL-05-004 exemption set
(DL-06-005).

**A type table holds only what this actor authored (DL-06-006).** A scan over
`list_objects("Create")` filtered on `actor == self` or on `context` answers "did
I send it" only while no received activity sits in that table under the sender's
id. A received copy must live in one receiver-keyed `ReceivedActivityRecord`,
archived or still held for a replay, never under the sender's id:
not at ingress, not in an effect node. A `StoreReceivedObjectNode` or
`idempotent_store` of the received activity itself breaks every such scan at once,
and the sender controls both the id and the unsigned `actor`. Source: #4866.

**The received archive is the sealed received body.** Store the body the parser
sealed and nothing derived from it; each load reparses it through the inbox's
parse and extraction into a read-only view. Reason: a stored summary silently
loses every field the extractor does not copy, so a reply built from it embeds
that summary instead of what the sender sent. Never add a second stored copy
beside the sealed body: two copies of one delivery drift. Source: ADR-0149.

## A DataLayer Fallback Is a Smell for a Masked Protocol Bug

Reading a protocol-significant field from the DataLayer *as a fallback* — when
that field could have arrived in the received message — is a smell for a masked
bug or race. A handler that falls back to `dl.read(...)` when
`event.activity.object_...` is absent usually works only because a prior
delivery happened to store the value: a hidden dependency on delivery order.

The smell does not apply when the message's copy is not authoritative. A field
that grants standing is read from the receiver's record of what it sent, never
from the copy the sender embeds. In `create_accept_invite_actor_to_case_tree`,
`SenderIsInviteeNode` (`vultron/core/behaviors/sender_entitlement/`) checks the
sender against the Invite the CASE_MANAGER recorded, and the invitee's roles come
from the participant record written when that Invite was sent. Taking them from
the copy inside the invitee's `Accept` lets any sender choose its own
(CM-11-017). A missing record is a refusal (CM-11-021,
`InviteeHasParticipantRecordNode`), not a cue to fall back.

**How to apply:**

- Read protocol-significant fields that are the sender's own assertion from the
  received message (`event.activity.object_...`).
- A **missing** protocol field is a protocol VIOLATION, not a cue to search the
  store: log it and return an empty/default result.
- DataLayer reads stay correct for **persisted state that cannot travel in the
  message** — the local `VulnerabilityCase` for derived fields, idempotency/dedup
  guards, correlation indexes.

This is the same message-primacy principle as DL-06-001/002 above and the
message-subject-identity rule in
[notes/wire-core-boundary.md](wire-core-boundary.md).

## Received Activity Artifacts: Inline Sub-Field Snapshots Are Intentional

A received Activity is an **artifact**: `_dehydrate_data` in
`vultron/adapters/driven/db_record/codec.py` deliberately does NOT recursively
dehydrate the sub-fields of an inline Activity object. When `Accept` stores an
inline `Offer`, the `Offer`'s own `object_`, `target`, etc. stay a snapshot of
what they contained at receipt time. Do not change this, for two reasons:

1. **Technical**: inline Activities may have no DataLayer record of their own
   (a reconstituted `Offer`, a `CaseLedgerEntry` inside an `Announce`, a
   `VulnerabilityCaseStub`), so collapsing them to an ID makes read-back
   rehydration impossible. A stub Invite is recognised by its target's `type`
   (CM-11-013), so a collapsed stub makes the stored Invite unrecognisable.
2. **Semantic (more important)**: an `Accept(Offer(VulnerabilityCase))` is a
   contract that records what was offered at the moment of acceptance. The case
   evolves; the contract must not.

**Two copies, not one.** An actor that extracts a case from a received
`Offer(VulnerabilityCase)` to seed its live record now holds the immutable
**artifact** (read it to answer "what was I offered?", never update it) and the
evolving **live record**. They diverge by design: never treat the snapshot as
current state, and never write it back over the live record.

Full design: `notes/wire-artifact-immutability.md`.

---

## Happy-Path DL Seeds Must Include Everything a Use Case Reads

A happy-path fixture MUST seed every record the use case reads to resolve a
related entity; an absent record makes an optional branch (such as a
notification) silently no-op while other nodes still emit, so `len(outbox) >= 1`
passes over the broken path. Assert the full count of activities the path must
emit, not `>= 1` (#1326).

---

## One Actor Id Is One Database

An `actor_id` is a **store name**, not a label on a store. `get_datalayer()`
requires an actor and returns that actor's own store (DL-07-002); there is no
unscoped singleton. A BT's store is the store of its executing actor, reconciled
once in `BTBridge._store_for_actor` (BT-05-005). Two hazards follow, in opposite
directions:

- **Two DataLayers built for the same actor id are the *same* database**
  (DL-07-004). Scenarios that must not see each other's rows need two actor ids;
  derive one per test (`f"{ACTOR_ID}/{slug}"`). The symptom is the second seed
  raising `ValueError: record with id_=... already exists`.
- **Sharing one store between two logical actors hides a *missing* write**: the
  reader finds the writer's row and the test passes for the wrong reason. Do not
  give one logical actor two ids merely to get a fresh database either; that
  reintroduces the masking.

`test/conftest.py` carries an autouse `_dispose_actor_stores_between_tests` —
**do not remove it.** It covers only the *between-test* case; both hazards above
occur *within* a single test (ADR-0073).

## Declaring a Test's Executing Actor

Because a BT's store follows its executing actor (BT-05-005), a test that
seeds one actor's store and runs `execute_with_setup(actor_id=<other>)` reads an
empty one. Declare the executor with `@pytest.mark.executes_as(ACTOR)` —
`bt_scenario` honours it — or build the scenario per actor with
`bt_scenario_factory`. Derive a test's executing actor from
`execute_with_setup(actor_id=…)` and `receiving_actor_id`, never from fixture or
test names.

---

## A Time Is Stated by Its Author, Never Minted by a Default

No model field defaults to the clock: an object's `published`, `updated` and an
embargo's `start_time` are required, and whatever builds the object states the act's
instant (ADR-0176, #5758). A minted default broke round trips — an equality held only
when write and read landed in the same wall-clock second (#3732) — and made an
object's time disagree with the act that made it.
`test/architecture/test_core_models_read_no_clock_default.py` refuses a new one.

- **A stored record without a required time is unsupported.** There is no
  migration and no fallback that fills one in; re-create the store.
- **A derived object that does not own a time states `None`.** An actor endpoint
  is an *address*: the core actor keeps it as a URI string (ARCH-12-006), so
  `_address_collection()` in `vultron/wire/as2/vocab/base/objects/actors.py` builds
  the wire collection with `published=None, updated=None`, while a collection that
  *arrives* carrying its own times keeps them as received (ADR-0103).
- **A received omission reads as `None`**, never as the receiver's clock
  (`absent_times_as_none`, ISSUE-3257); a time the class requires non-null is then
  refused at validation.
- **A round-trip equality test must cross a second boundary on purpose.** Step the
  clock between write and read with `SteppingClock` from
  `vultron/demo/determinism.py`; never `time.sleep()`.

## A Read-Modify-Write of a Shared Record Uses `save_if_unchanged`, Not `save`

`save()` is an unguarded upsert: a caller that reads a record, changes one field
and saves it back overwrites any write that landed in between. For a
read-modify-write of a shared record, use `DataLayer.save_if_unchanged(obj,
expected)` (DL-02-003), which writes only when the stored record still equals
`expected` and otherwise returns `False` with nothing written. It closes both the
window before the call and the window between its own read and write; the tests
are in `test/adapters/driven/test_sqlite_save_if_unchanged.py`.

- **The caller decides what a refusal means.** A caller that changes one field
  can re-read and re-apply, then refuse after a bounded number of attempts (the
  embargo-policy PUT answers 409, EP-02-009). A caller whose change depends on the
  fields it read must surface the conflict at once.
- **A compare-and-set guards only the writers that use it.** Every
  read-modify-write of the actor profile MUST go through `save_if_unchanged`; a
  plain `save()` by a new profile writer reopens the lost-write window (#4102).
  `POST /actors/` uses `create()`, which refuses an existing record.

---

## Writes That Must Land Together Use `transaction()`

`with dl.transaction():` makes every call on that store, from that thread, one
SQLite transaction: it commits once at the end, or rolls everything back when the
block raises (DL-02-004, ADR-0146, CLP-07-015). The rules that keep it sound:

- **Every session goes through `SqliteDataLayer._session()`.** Inside the block
  that seam binds the session to the block's connection and joins it by
  SAVEPOINT, so a helper's `commit()` commits nothing early and its `rollback()`
  undoes only its own writes. A raw `engine.connect()` inside the block bypasses
  it; on an in-memory store it shares the one connection and its close rolls the
  whole block back (#3602).
- **A read takes its connection from `SqliteDataLayer._connection()`.** It runs a
  prebuilt Core `select` there, never an ORM `Session`, because the session cost
  most of a read (#4969). Inside the block that seam yields the block's own
  connection, so the read sees the block's writes. It is for reads only: a write
  on it skips the SAVEPOINT that `_session()` gives.
- **An object-row write forgets the rows it touches.** The block keeps each row
  it reads and serves a second read of it without a fetch (DL-02-011, #5344),
  which is sound only because every `vultron_objects` write calls
  `forget_rows()` first. A new write path that skips it hands later reads in the
  block the row's old version; write through `crud`, or call `forget_rows()`.
- **Side effects outside the store wait for the commit.** The outbox enqueue
  callback runs through `run_after_commit()`; anything else that tells another
  thread a row exists does the same, or it signals a row that may roll back.
- **One store only.** The block covers the store it was opened on; a write to
  another actor's store inside it commits on its own.
- **Keep it short.** It takes the write lock (`BEGIN IMMEDIATE`) and, in memory,
  the session lock, so other writers wait for the whole block. A waiter can be
  the event loop (the outbox drain writes synchronously), and on a file store a
  wait past SQLite's busy timeout (5 s by default) raises `database is locked`.
  An `ActTransaction` holds the lock for a whole act's effects, so keep slow or
  external work (a call-out, another store) out of it.

---

## Retiring a Stored Field (Rename, Move, or Delete)

Before 1.0 Vultron supports one storage version (ADR-0175), so a renamed, moved,
or deleted persisted field gets no read alias (`AliasChoices`), no conversion and
no list of its former names.
Drop the field from the model and nothing else: a row that still carries the old
key is refused by `extra="forbid"` like any other unknown key (MV-11-004,
ARCH-12-003), with the generic "extra inputs are not permitted" error.
Never add a guard that refuses the old key by name (MV-11-012): it is upkeep that
nobody reads once the store is reset.
The SQLite read path logs the validation reason at WARNING when it reads such a
row as absent, so `dl.read()` returning `None` always has a logged cause.
Every PR that retires a stored field carries an operator note saying a file-backed
store must be reset (`docker compose down -v`); an in-memory store is unaffected.

A deleted stored *type* needs no marker either, only that operator note.
Keeping the name alive for old rows is the shim PROTO-08-003 forbids.
The read is already legible: the vocabulary miss logs a WARNING naming the
type and the row reads as absent (`test_sqlite_core_roundtrip.py`, #4940).

## Changing a Table's Shape

A store written before a table gains a constraint or index is refused when it
is opened, never migrated and never run without the guarantee. `create_all`
creates a missing table with its indexes but never alters one that exists, so
an old store would otherwise open silently and fail later, at the first write
that relies on the new shape. Check the new shape after `create_all` in
`SqliteDataLayer.__init__` and raise `VultronStaleStoreError` saying the store
must be reset. The outbox no-duplicate index is the
example: `require_outbox_pending_index` in `datalayer_sqlite/schema.py` (#4629).
