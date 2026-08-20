---
title: "DataLayer Design: Architecture and Migration Notes"
status: active
tags: [datalayer, ports, persistence, architecture, migration, hexagonal]
description: >
  Architectural analysis of the DataLayer port contract, CasePersistence
  narrowing, auto-rehydration requirements, storage record design, and
  vocabulary registry entanglement. Operating rules live in
  vultron/core/ports/AGENTS.md.
related_specs:
  - specs/datalayer.yaml
  - specs/architecture.yaml
related_notes:
  - notes/domain-model-separation.md
  - notes/architecture-hexagonal.md
  - notes/activitystreams-semantics.md
relevant_packages:
  - vultron/core/ports
  - vultron/adapters/driven
  - vultron/wire/as2/vocab
---

# DataLayer Design: Architecture and Migration Notes

Operating rules summary: `vultron/core/ports/AGENTS.md`.
Specs: `specs/datalayer.yaml` (DL-01 through DL-04).

## DataLayer vs. CasePersistence

The repository distinguishes between two layers of persistence contract:

| Port | Intended callers | Purpose |
| --- | --- | --- |
| `DataLayer` | adapters, routers, infrastructure code | Full adapter-level contract, including persistence, queue operations, health/admin helpers, and diagnostics |
| `CasePersistence` | core use cases and BT nodes | Narrow core-facing persistence/query contract |
| `CaseOutboxPersistence` | the small subset of core code that also enqueues outbound activities | `CasePersistence` plus outbound enqueue methods only |

`CasePersistence` is intentionally narrower than `DataLayer`. Its current
required minimum surface is:

- `create`
- `read`
- `get`
- `save`
- `by_type`
- `find_case_by_report_id`
- `find_actor_by_short_id`

That list is the current minimum contract, not a promise that the
surface is finished forever. Future additions are allowed only when they
preserve the same core-facing persistence/query boundary. Queue methods,
health checks, admin helpers, diagnostics, and low-level storage
primitives remain part of the full `DataLayer` contract instead.

## Deprecated Compatibility Methods

`get()` and `by_type()` remain on `CasePersistence` only as compatibility
methods during the migration away from raw-record access in core. They
are deprecated and should be treated as removal targets, not stable
design endpoints.

For new or refactored core code, prefer:

- `read()` for single-object lookup
- `list_objects()` for typed collection queries
- dedicated typed helper methods when a generic query would otherwise
  expose raw persistence details

## CaseOutboxPersistence as a Smell Marker

`CaseOutboxPersistence` exists for the small amount of core code that
must both update case state and enqueue outbound activities. That need is
sometimes legitimate, but it should not become invisible. When a
`ReceivedUseCase` depends on `CaseOutboxPersistence`, treat that as an
architectural smell: the handler is mixing inbound processing with
outbound broadcast and should be reviewed for a cleaner split later.

## Auto-Rehydration: `dl.read()` MUST Return Fully Typed Objects

The DataLayer port MUST guarantee that `dl.read(id)` and
`dl.list_objects(type_key)` always return fully rehydrated, typed domain
objects — never raw storage records, untyped dicts, or objects with
dehydrated string references in nested fields.

**Rationale**: the SQLite DataLayer adapter currently dehydrates nested
object references to ID strings on write. Without auto-rehydration on
read, every use case that retrieves an activity with a nested object must
manually coerce the dehydrated string back to a typed object via
`model_validate`. That duplication:

- directly caused the INLINE-OBJ-B bugs (bare string `object_` values
  passing through to Accept/Reject constructors)
- repeats the same strip-and-validate boilerplate across multiple use
  cases
- violates the hexagonal principle that core should not know about
  storage internals

Auto-rehydration applies to **all fields that the adapter dehydrates**:

- `object_` — the primary offender (transitive activity nested object)
- `target` — target object reference
- `origin` — origin object reference
- any other field that `_dehydrate_data` currently collapses to an ID
  string

Once the DataLayer adapter implements auto-rehydration on read, all
manual coercion code in use cases MUST be removed. Search targets
include:

- `vultron/core/use_cases/triggers/embargo.py`
- `vultron/core/use_cases/triggers/report.py`
- `vultron/core/use_cases/received/sync.py`
- any other site calling `model_validate` after `dl.read()` to recover
  nested object type information

Specs: `specs/datalayer.yaml` DL-01-001 through DL-01-004.

## Core Should Reliably Get Domain Objects from DataLayer

Core should be able to call `dl.read(id)` or `dl.list(type_key)` and
receive properly typed domain objects rather than raw SQLite records,
untyped dicts, or ambiguous `StorableRecord` types.

Conversely, when persisting objects, core should be able to call
`dl.save(domain_obj)` and trust that the adapter handles the translation
to whatever storage format is needed. Core should not need to call
`object_to_record()` or know anything about storage internals.

Symptoms of an unhealthy boundary include:

- `record_to_object()` being called in core use cases to convert
  DataLayer results back into domain objects
- `object_to_record()` being called in core use cases before
  `dl.update()`
- type checks like `if isinstance(result, Document): ...` appearing in
  core, revealing DataLayer implementation details in business logic

Recommended direction:

1. `dl.read(id)` returns a typed, fully rehydrated domain object (or
   raises `VultronNotFoundError`).
2. `dl.save(obj)` accepts domain objects directly and handles all
   serialization internally.
3. `dl.list(type_key)` returns an iterable of typed, fully rehydrated
   domain objects.
4. All `object_to_record()` / `record_to_object()` calls move into the
   adapter.

A mapping layer between core objects and DataLayer records belongs in the
adapter, not in core. This improves separation of concerns and makes core
logic easier to test without mocking storage internals.

This is also why `get()` and `by_type()` are a poor long-term fit for
`CasePersistence`: they keep raw-record style access available to core
when the target direction is fully typed domain-object access.

## DataLayer Storage Records Need Re-Evaluation

`Record` and `StorableRecord` in
`vultron/adapters/driven/db_record.py` were designed when wire and core
were the same layer. Now that they are separated, these classes need
re-evaluation. The questions to answer are:

1. Should `Record`/`StorableRecord` remain as adapter-specific types, or
   should they be promoted to a more neutral abstraction?
2. Is a tiered adapter structure appropriate — a thin translation adapter
   that converts domain objects to/from a generic dict/document form,
   sitting above a storage-specific adapter (SQLite, MongoDB, SQL)?
3. How should the DataLayer port be typed: should it use generic
   `dict`/`Any` for storage records, or should there be typed protocols
   for different record kinds?

**Key principle**: the DataLayer **port** should be defined entirely in
terms of core domain objects. The DataLayer **adapter** handles all
translation to storage format. Core should be agnostic to whether the
adapter uses separate tables per type, a single JSON blob, or a document
store.

Research needed: audit all current callers of `object_to_record()`,
`record_to_object()`, and `find_in_vocabulary()` to understand the scope
of the coupling before designing the refactor.

## Read Path MUST Return Core Objects (ADR-0034, DL-05)

**Decided (ADR-0034):** `dl.read()` and `dl.list_objects()` MUST return
**core** domain objects (`vultron/core/models/`), never **wire** vocabulary
types (`vultron/wire/as2/vocab/objects/`, `as_`-prefixed), for any persisted
`type_` that has a registered core counterpart in `CORE_VOCABULARY`.

**Implemented (PR #1529):** The read path now reconstructs domain entities via
`CORE_VOCABULARY`, so `dl.read()` returns core objects. The duck-typing
Protocols and `TypeGuard` helpers (`CaseModel`, `is_case_model()`, etc.) in
`vultron/core/models/protocols.py` were removed; core uses direct
`isinstance()` checks against concrete core classes (DL-05-003).

DL-05 end-state achieved (all four requirements met):

1. The adapter reconstructs registered domain entities via
   `find_in_core_vocabulary()` / `CORE_VOCABULARY`, so reads/writes of domain
   entities are core → core.
2. The adapter owns wire↔core translation and keeps its own
   `type_`→core-class mapping, independent of the wire `VOCABULARY`.
3. The duck-typing Protocols in `protocols.py` are removed; core depends on
   concrete core classes (real `isinstance` narrowing).
4. A ratchet test asserts no `vultron.wire.as2` vocabulary type escapes
   `dl.read()` / `dl.list_objects()` into `vultron/core/`.

**Recognised exception — AS2 Activities.** The 29 protocol message types
(`vultron/wire/as2/vocab/activities/`) have no core counterpart, so they
cannot be returned as core objects. Core code that reads a stored wire
Activity back from the DataLayer (e.g. `dl.read(offer_id)` returning an
`as_Offer`) is itself a boundary violation (ARCH-01-002, ARCH-03-001), but
migrating it out of core is tracked as a **separate concern** (#1506, decided
in ADR-0035), not part of the DL-05 entity work. Until then, the ratchet
exemption set enumerates these Activity types explicitly so it can only shrink.

## Write Path Normalises Wire → Core (#2232, ADR-0062)

The read-path rule above says nothing about what gets *written*, and that gap
was load-bearing. `Record.from_obj()` rejected objects whose `type_` starts with
`as_` — but wire vocabulary `type_` values are **bare** (`"CaseParticipant"`, not
`"as_CaseParticipant"`), so the guard never fired for the 15 wire classes that
shadow a `CORE_VOCABULARY` entry. A wire-shaped object was written into a
core-typed row, and whichever class read the row back decided what the data
meant.

For `ParticipantStatus` and `CaseParticipant` the two shapes are *structurally*
incompatible — core nests `rm: RmDimension` where wire carries a flat `rm_state`
— so a wire-shaped row makes `status.rm.state` yield `None` rather than merely
misspell a key.

**Rule:** `Record.from_obj()` normalises through `_normalize_to_core()`
(`vultron/adapters/driven/db_record.py`) before serialising. The object **and its
direct children** are projected via `to_core()`; one level of children is
sufficient because `to_core()` recurses. Child projection is not optional
polish: a `VulnerabilityCase` row stores its `case_participants` inline, so
checking only the top level still persisted a flat `rm_state` inside a
core-shaped case.

`_NORMALIZE_WIRE_TO_CORE` enumerates the migrated types. It is the write-side
analogue of `KNOWN_WIRE_ESCAPES` and ratchets the opposite way — it may only
**grow** (`test/architecture/test_normalize_wire_to_core_ratchet.py`). The
remaining 5 shadowing types are all actor types (`VultronApplication`,
`VultronGroup`, `VultronOrganization`, `VultronPerson`, `VultronService`);
none has a `to_core()` projection yet — tracked in #2268.

**`StorableRecord` inputs to `create()` and `update()` are also normalised.**
`crud.create()` and `crud.update()` receive `StorableRecord` from core BT nodes
(e.g. `CreateObject`, `UpdateObject` in `vultron/core/behaviors/helpers.py`).
Before #2283 these bypassed the normalisation entirely. The fix routes them
through `_storable_to_record()` (`vultron/adapters/driven/datalayer_sqlite/crud.py`),
which gates the same `to_obj()` → `from_obj()` round-trip on `record.type_ in
_NORMALIZE_WIRE_TO_CORE`, preserving other types verbatim to avoid data loss
on polymorphic wire classes (e.g. `VultronPerson` stored under `type_="Actor"`
would be silently truncated to the base class). If the round-trip fails for a
type that is in `_NORMALIZE_WIRE_TO_CORE`, a `WARNING` is logged and the row is
stored verbatim — a regressive fallback, but observable.

**A projection failure raises `VultronValidationError`, not `ValueError`.**
`crud.create()` raises `ValueError` for an already-existing row and callers
legitimately swallow *that*; sharing the type meant an unprojectable object was
silently never stored and never logged. The two causes must stay distinguishable
— see `_pre_store_nested_object` in
`vultron/adapters/driving/fastapi/routers/actors/_inbox.py` for the correct
two-branch handler.

**This is defense in depth, not the primary boundary.** Projection belongs at
wire→core ingress; the persistence boundary is the backstop that guarantees no
wire-shaped row exists regardless of which ingress path missed it. ADR-0062
records why both are kept.

## Activity Read-Back: Semantic Content vs. Envelope Reconstitution (ADR-0035, DL-06)

**Decided (ADR-0035).** `dl.read(activity_id)` in `vultron/core/` is a
*symptom*. The root cause is that the 29 AS2 protocol Activities (`Offer`,
`Invite`, `Accept`, …) were built wire-first and never given a core counterpart,
inverting "wire is a projection of core" (ADR-0017) and violating ARCH-09-001.
Because the domain fact each message carries has no home in core, core reaches
back through the DataLayer to re-read the stored wire envelope.

Vultron is a set of communicating **core** state machines; wire exists only to
carry a core fact from one isolated actor to another (Actor Knowledge Model). An
AS2 Activity is an **envelope**, not a domain object. The fix splits two needs
that `dl.read(activity_id)` conflates:

| Need | Source of truth | Rule |
|---|---|---|
| **Semantic content** — what a message *means* | **Core state** | Core MUST NOT re-read the activity to interpret it (DL-06-001, DL-06-002). |
| **Correlation** — which prior message this answers | **Core-entity relationship** | Resolve through a domain relationship, not a wire re-read (DL-06-003). |
| **Envelope reconstitution** — verbatim original in a reply's `object_` | **Stored opaque activity payload** | MAY read a stored activity, but only via a wire/adapter seam that never interprets it (DL-06-004). |

The extractor (the single interpretation site, ARCH-03-001) records each domain
fact as core state at interpretation time — a transition on an existing core
entity or a purpose-built core record. This is **not** a 1:1 clone of the AS2
Activity into core (the generic-event-mirroring-AS2 anti-pattern in
`notes/domain-model-separation.md`); model only the domain fact, in domain
vocabulary, capturing only what handlers use.

**Why the envelope seam is legitimate, not anathema.** Activity ids are
non-regenerable random `urn:uuid:` values (`vultron/wire/as2/vocab/base/utils.py`),
and the Actor Knowledge Model requires a reply to embed the *full inline
original* activity — so a reply's `object_` cannot be produced by re-projecting
core state. The original envelope must be retained and read back verbatim.
Confining that read to a wire/adapter-owned seam that treats the payload as
opaque keeps semantic authority in core. `CaseLedgerEntry.payloadSnapshot` is
the existing precedent for opaque, write-only activity retention.

### Audited core activity read-back sites (concern #1506)

Classification of every `dl.read(activity_id)` / activity `list_objects()` site
in `vultron/core/` at audit time. Categories A/B need migration; C is the
sanctioned seam; D is not an activity read (covered by DL-05 / #1503).

**A — plumbing re-reads** (re-read only to `model_dump()` the just-emitted
activity into the API response; the factory already built the object):

- `vultron/core/use_cases/triggers/report.py` — `_handle_result` in
  `SvcValidateReportUseCase`, `SvcInvalidateReportUseCase`, `SvcRejectReportUseCase`,
  `SvcCloseReportUseCase` (4 sites).
- ~~`vultron/core/behaviors/case/nodes/delegation.py`~~ — `CreateOfferCaseManagerActivityNode`
  re-read the just-created `Offer(CaseManagerRole)`. Deleted in issue #2429 when
  `OFFER_CASE_MANAGER_ROLE` infrastructure was removed (ADR-0039).
- *Fix*: `TriggerActivityPort` returns `(activity_id, activity_dict)`; delete the
  re-reads. Not even a semantic read.

**B — semantic-content reads** (core re-interprets a stored activity for a
domain fact — the ARCH-09-001 core violations):

- ~~*report/offer*~~: migrated (#1518). `VultronOfferRecord` now captures
  offer facts at adapter time (sender) and received-side ingest time (receiver).
  Core reads `VultronOfferRecord` instead of the stored wire `Offer` activity.
- ~~*embargo*~~: migrated (#1519). `pending_embargo_proposal_index: dict[str,
  str]` (embargo_id → proposal_id) added to `VulnerabilityCase`; populated on
  receive (`InviteToEmbargoOnCaseReceivedUseCase`) and trigger
  (`SvcProposeEmbargoUseCase._handle_result`). All `dl.read(invite_id)` and
  `list_objects("Invite")` semantic reads in `received/embargo.py`,
  `triggers/_helpers.py`, and `dispatcher.py` removed. `Invite` removed from
  DL-05-004 exemptions.
- ~~*actor/participant*~~: migrated (#1520). `recommendation_recommender_index:
  dict[str, str]` (recommendation_id → recommender_actor_id) added to
  `VulnerabilityCase`; populated in `OfferActorToCaseReceivedUseCase.execute()`.
  `AcceptOfferCaseParticipantReceivedUseCase` and
  `RejectOfferCaseParticipantReceivedUseCase` now read
  `case.recommendation_recommender_index.get(recommendation_id)` instead of
  `dl.read(recommendation_id)`. Redundant `invite_type != "Invite"` check
  removed from `SvcAcceptCaseInviteUseCase._prepare()`.
- *Fix*: capture the fact as core state at extraction time; read it from core.

**C — envelope reconstitution** (verbatim original needed for a reply):

Audited by #1521. Four live reply paths need the verbatim original activity
inline in the reply's `object_`:

- `TriggerActivityAdapter.accept_case_invite` (`actors.py`) — reads the
  stored `Invite` and passes it verbatim to `rm_accept_invite_to_case_activity`.
- `TriggerActivityAdapter.accept_embargo` (`embargo.py`) — reads the stored
  embargo proposal `Invite` and passes it to `em_accept_embargo_activity`.
- `TriggerActivityAdapter.reject_embargo` (`embargo.py`) — same pattern for
  `em_reject_embargo_activity`.
- `TriggerActivityAdapter.accept_case_participant_offer` (`actors.py`) —
  reads the stored `Offer(CaseParticipant)` and passes it to
  `accept_case_participant_offer_activity`.

**All four reads are already in the adapter layer** (`vultron/adapters/driven/
trigger_activity_adapter/`), not in `vultron/core/`. They satisfy DL-06-004:
the payload is treated opaquely (passed straight to the factory without any
semantic interpretation). No new seam is needed; the correct seam already
exists. The DL-05-004 exemption set does not need modification for these sites
because they are not core reads.

Tests verifying verbatim reconstitution (id preserved in `in_reply_to` /
`object.id`) are in `test/adapters/driven/trigger_activity_adapter/`.

**D — not activities** (core entities, covered by DL-05 / #1503, out of scope):

- `dispatcher.py:147` (`VultronReplicationState`); `received/actor/announce.py:29`
  (`VultronReportCaseLink`); `list_objects("CaseLedgerEntry")` reads; case /
  participant / status / marker reads.

Implementation is tracked in the issues filed from concern #1506 (blocked by
that concern, children of Epic #1394). As each B site migrates, remove its
Activity type from the DL-05-004 exemption set (DL-06-005) until the set reaches
zero.

## Vocabulary Registry Entanglement Across Wire, Core, and DataLayer

The vocabulary registry in `vultron/wire/as2/vocab/` was created before
the hexagonal architecture separated wire from core. As a result:

- `vultron/adapters/driven/db_record.py` uses the vocabulary registry to
  determine AS2 type names for storage keys.
- `vultron/wire/as2/rehydration.py` uses the vocabulary registry to
  reconstruct wire objects from DataLayer records.
- these two files create a tight coupling: the DataLayer's behaviour
  depends on the wire layer's type system.

If the wire layer is removed or replaced, the DataLayer adapter breaks.
Core cannot interact with the DataLayer in terms of core domain objects
because the adapter expects to find AS2 type names at every step.

Recommended direction:

1. The DataLayer adapter should maintain its own type-to-table mapping
   that is independent of the wire vocabulary registry.
2. Rehydration of wire objects from storage should be confined to the
   wire adapter layer, not shared with core.
3. Core's interaction with the DataLayer should use core domain type keys
   (`"VultronCase"`, `"VultronReport"`, etc.) rather than AS2 type
   names (`"Case"`, `"VulnerabilityReport"`, etc.).

This separation allows the wire layer to evolve (or be replaced) without
breaking DataLayer storage, and allows core to read/write domain objects
without knowing anything about AS2 naming conventions.

Files to investigate:

- `vultron/adapters/driven/db_record.py`
- `vultron/adapters/driven/datalayer_sqlite.py`
- `vultron/wire/as2/rehydration.py`
- `vultron/wire/as2/vocab/registry.py`

---

## `outbox_list()` Requires `clone_for_actor` in Tests

(ISSUE-1298, 2026-07-10)

`SqliteDataLayer.outbox_list()` reads the outbox for `dl._actor_id`, which is
`""` on a freshly constructed `SqliteDataLayer("sqlite:///:memory:")`. BT nodes
call `record_outbox_item(actor_id, activity_id)`, writing to the named actor's
queue. The two paths do not share the same key unless the DataLayer was obtained
via `clone_for_actor(actor_id)`.

**In tests that verify outbox contents after use-case execution:**

```python
# ✅ CORRECT — read by explicit actor ID
outbox = dl.outbox_list_for_actor(local_actor_id)

# ✅ ALSO CORRECT — clone before reading (matches BT pattern)
actor_dl = dl.clone_for_actor(actor_id)
outbox = actor_dl.outbox_list()

# ❌ WRONG — returns [] unless dl._actor_id was set
outbox = dl.outbox_list()
```

---

## Happy-Path DL Seeds Must Include Origin Activities for `dl.read()` Calls

(ISSUE-1326, 2026-07-10)

When a use case calls `dl.read(some_id)` to resolve a related entity (e.g.,
`recommender_id` from the original recommendation offer), the happy-path test
fixture MUST store that entity in the DataLayer, or the use case silently falls
back to `""` / `None`.

In `AcceptActorRecommendationReceivedUseCase` and
`RejectActorRecommendationReceivedUseCase`, the `origin` field of the inner
`Offer(CaseParticipant)` carries the original recommendation activity ID. The
use case calls `self._dl.read(recommendation_id)` to look up that activity and
extract `recommender_id`. If the activity is absent, `recommender_id=""` and the
recommender-notification branch silently no-ops — but other tree nodes still emit
to the outbox, so `len(outbox) >= 1` can pass while hiding the broken path.

**Fix pattern**: after building the inner offer with
`origin=<recommendation_id>`, also call
`dl.create(recommend_actor_activity(..., id_=<recommendation_id>))` in the
fixture so `dl.read()` resolves correctly.

**Assertion depth**: the Accept happy path emits both an Accept notification
and an Invite (2 activities). Assert `len(outbox) >= 2`, not `>= 1`, to catch
the case where only one of the two required activities was emitted.

---

## Dual-DataLayer Isolation Guard in Tests

(ISSUE-1749, 2026-08-08)

A single-DataLayer test cannot catch a BT node that accidentally calls
`get_datalayer()` (the process-global singleton) instead of `self.datalayer`.
Such a node writes records to the singleton while the injected DataLayer stays
empty — all positive assertions on the injected DL still pass.

**The dual-DL isolation pattern** uses two separate in-memory DataLayer
instances and asserts the global singleton is empty after the BT runs:

```python
from vultron.adapters.driven.datalayer_sqlite import get_datalayer, reset_datalayer
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

@pytest.fixture(autouse=True)
def _reset_singleton(self):
    reset_datalayer()
    yield
    reset_datalayer()

def test_records_on_injected_dl_not_singleton(self, make_payload):
    case_actor_dl = SqliteDataLayer("sqlite:///:memory:")  # injected DL
    _seed_and_run(make_payload, case_actor_dl)

    assert list(case_actor_dl.list_objects("VulnerabilityCase")), \
        "record must appear on the injected DataLayer"
    assert not list(get_datalayer().list_objects("VulnerabilityCase")), \
        "singleton must stay empty — a get_datalayer() call in the BT node would fail this"
```

Key points:

- `reset_datalayer()` before **and** after each test ensures test order
  independence — a previous test that did call `get_datalayer()` won't poison
  the singleton check.
- `get_datalayer()` called with no arguments returns the shared/admin singleton
  (unscoped). It is never the same object as `SqliteDataLayer("sqlite:///:memory:")`
  created directly — the two have independent backing stores.
- Apply this pattern for any BT-backed use case that receives a DataLayer as a
  constructor argument: `CreateCaseProposalReceivedUseCase`,
  `SvcCreateCaseUseCase`, and any future CaseActor-initialisation BTs.

Reference: `test/core/behaviors/case/test_case_proposal_received_tree.py`,
class `TestCreateCaseProposalReceivedBTCaseActorRecords`.
