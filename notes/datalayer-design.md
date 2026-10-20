---
title: "DataLayer Design: Architecture and Migration Notes"
status: active
kind: guidance
tags: [datalayer, ports, persistence, architecture, hexagonal]
description: >
  Rules for the DataLayer port contract, CasePersistence narrowing, the
  write/read shape boundary, activity read-back, the received archive as the
  sealed body, received-activity keying, received-artifact snapshots, per-actor
  stores, shared-record writes, and stored-shape changes. Operating rules live in vultron/core/ports/AGENTS.md.
related_specs:
  - specs/datalayer.yaml
  - specs/architecture.yaml (ARCH-12-003, ARCH-12-006, ARCH-23-003, ARCH-23-005)
  - specs/embargo-policy.yaml (EP-02-004)
  - specs/case-management.yaml (CM-11-017)
  - specs/outbox.yaml (OX-06-002)
  - specs/inbox-endpoint.yaml (IE-10-001)
  - specs/vocabulary-model.yaml (VM-08-002)
related_notes:
  - notes/architecture-hexagonal.md
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
  - vultron/adapters/driven
  - vultron/wire/as2/vocab
---

# DataLayer Design: Architecture and Migration Notes

Operating rules summary: `vultron/core/ports/AGENTS.md`.
Specs: `specs/datalayer.yaml`.

`dl.read()` returns core objects, never wire objects (ADR-0034), and core
reads a received activity's facts only from the read-only view its archive loads
(ADR-0149; #4943 rewrites DL-06-001 and DL-06-002 to match; see "Activity
Read-Back" below).

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

## CaseOutboxPersistence as a Smell Marker

`CaseOutboxPersistence` exists for the small amount of core code that
must both update case state and enqueue outbound activities. That need is
sometimes legitimate, but it should not become invisible. When a
`ReceivedUseCase` depends on `CaseOutboxPersistence`, treat that as an
architectural smell: the handler is mixing inbound processing with
outbound broadcast and should be reviewed for a cleaner split later.

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
  `vultron/adapters/driven/datalayer_sqlite/hydration.py`
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
| **Semantic content** — what a message *means* | **Core state**, or the archive's read-only view | Core reads a received activity's facts only from the view its archive loads, never from a wire row (ADR-0149; #4943 rewrites DL-06-001 and DL-06-002 to match). |
| **Correlation** — which prior message this answers | **Core-entity relationship** | Resolve through a domain relationship, not a wire re-read (DL-06-003). |
| **Envelope reconstitution** — verbatim original in a reply's `object_` | **The archived sealed body** | Read only via a wire/adapter seam that parses the sealed body; never the core summary (DL-06-004, ADR-0149). |

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
(`vultron/adapters/driven/trigger_activity_adapter/`), which passes the stored
payload to the factory without interpreting it. As a core site migrates, remove
its Activity type from the DL-05-004 exemption set (DL-06-005).

**A type table holds only what this actor authored (DL-06-006).** A scan over
`list_objects("Create")` filtered on `actor == self` or on `context` answers "did
I send it" only while no received activity sits in that table under the sender's
id. A received copy must live in a receiver-keyed `ReceivedActivityRecord` or an
opaque deferred record, never under the sender's id: not at ingress, not in an
effect node. A `StoreReceivedObjectNode` or `idempotent_store` of the received
activity itself breaks every such scan at once, and the sender controls both the
id and the unsigned `actor`. Source: #4866; work: #4869, #4870, #4871.

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
`SenderIsInviteeNode` (`vultron/core/behaviors/sender_entitlement.py`) checks the
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
`vultron/adapters/driven/db_record.py` deliberately does NOT recursively
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
`Offer(Case)` to seed its live record now holds the immutable **artifact** (read
it to answer "what was I offered?", never update it) and the evolving **live
record**. They diverge by design: never treat the snapshot as current state, and
never write it back over the live record.

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

## A Clock-Minted Default Cannot Round-Trip Through a Field That Does Not Store It

A value a wire default mints at construction cannot survive a round trip through
a core field that does not store it; the symptom is an equality that holds only
when write and read land in the same wall-clock second (#3732). Neither "store
more" nor "re-mint on read" is the fix — the fix is to stop minting. For example,
an actor endpoint is an *address*: the core actor keeps it as a URI string
(ARCH-12-006), so `_address_collection()` in
`vultron/wire/as2/vocab/base/objects/actors.py` builds the derived wire
collection with `published=None, updated=None`, while a collection that
*arrives* carrying its own times keeps them as received (ADR-0103).

- **A round-trip equality test must cross a second boundary on purpose.** Step
  the clock between write and read with `SteppingClock` from
  `test/support/clock.py`; never `time.sleep()`.
- **Ask which side of the boundary owns a default before adding one.** If a
  field defaults on the wire branch and the core branch reduces the object to a
  reference, the default is unstorable and every read disagrees with every write.

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
  embargo-policy PUT answers 409, EP-02-004). A caller whose change depends on the
  fields it read must surface the conflict at once.
- **A compare-and-set guards only the writers that use it.** Every
  read-modify-write of the actor profile MUST go through `save_if_unchanged`; a
  plain `save()` by a new profile writer reopens the lost-write window (#4102).
  `POST /actors/` uses `create()`, which refuses an existing record.

---

## Renaming a Stored Field

Stored data carries no backwards compatibility. A renamed persisted field gets
no read alias (`AliasChoices`) and no conversion: the model declares the old key
in `retired_stored_fields` via `RetiredFieldsRecord`
(`vultron/core/models/retired_stored_fields.py`), and a row that still carries
it, in either the field-name or camelCase spelling, fails to load with a
message naming the old shape and saying the store must be reset (#4128). Every
retired key the row carries is reported, not only the first (EH-07-001), and a
retirement table whose replacement the model does not declare, or whose old key
it still declares, fails at class definition.

The declaration is what makes the refusal legible. `CoreRecord` refuses unknown
keys (`extra="forbid"`), so an undeclared rename never loses a field silently,
but the row fails with a bare "extra inputs are not permitted" plus a "field
required" for a name the operator never wrote, and nothing says a rename
happened. The SQLite read path logs the validation reason at WARNING when it
reads such a row as absent, so `dl.read()` returning `None` always has a logged
cause. Every PR that renames a stored field carries an operator note saying a
file-backed store must be reset (`docker compose down -v`); an in-memory store is
unaffected.

## Changing a Table's Shape

A store written before a table gains a constraint or index is refused when it
is opened, never migrated and never run without the guarantee. `create_all`
creates a missing table with its indexes but never alters one that exists, so
an old store would otherwise open silently and fail later, at the first write
that relies on the new shape. Check the new shape after `create_all` in
`SqliteDataLayer.__init__` and raise `VultronStaleStoreError` saying the store
must be reset, as for a renamed field. The outbox no-duplicate index is the
example: `require_outbox_pending_index` in `datalayer_sqlite/schema.py` (#4629).
