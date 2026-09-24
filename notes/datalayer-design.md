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
  - notes/wire-core-boundary.md
  - notes/testing-pitfalls.md
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

- `read_case()` for `VulnerabilityCase` retrieval — returns the typed object
  directly, no isinstance narrowing needed (ISSUE-2490)
- `read()` for single-object lookup of other domain types
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

## Write Path Stores Verbatim; the Boundary Is `extra="forbid"` (#2232, #2940)

**Superseded (#2940).** The write-side normalisation gate this section used to
describe — `Record.from_obj()` projecting through `_normalize_to_core()`, the
`_NORMALIZE_WIRE_TO_CORE` frozenset, its grow-only ratchet, and
`_project_shadowing_wire_obj` — **is deleted**. ADR-0062 is archived; the
contract is now ADR-0082 / ARCH-12-003.

The problem it solved was real and is worth keeping in view: `Record.from_obj()`
rejected objects whose `type_` starts with `as_`, but wire vocabulary `type_`
values are **bare** (`"CaseParticipant"`, not `"as_CaseParticipant"`), so the
guard never fired for the 15 wire classes that shadow a `CORE_VOCABULARY` entry.
A wire-shaped object was written into a core-typed row, and whichever class read
the row back decided what the data meant. For `ParticipantStatus` and
`CaseParticipant` the two shapes are *structurally* incompatible — core nests
`rm: RmDimension` where wire carries a flat `rm_state` — so a wire-shaped row
makes `status.rm.state` yield `None` rather than merely misspell a key.

**Rule (current):** the guard moved from the write path to the *type*.
`CoreObject` sets `extra="forbid"` (ARCH-12-003), so handing a wire-shaped
payload to a core type raises a pydantic `ValidationError` instead of silently
discarding every snake_case-only key. Two consequences for this adapter:

- **Writes store verbatim.** `Record.from_obj()` and `_storable_to_record()` no
  longer project anything; a row is persisted in whatever shape it arrived.
- **Reads project.** `ValidationError` is the shape-mismatch signal that drives
  the read-side fallback (`_from_row` → `_wire_object_from_row` →
  `_project_wire_row_to_core`), so a wire-shaped row still reads back as core.
  When even that projection fails, `dl.read()` logs a WARNING and returns the
  **wire** object (see "A DataLayer Fallback Is a Smell for a Masked Protocol
  Bug" below).

Two caveats worth knowing before touching this path:

- `extra="forbid"` rejects *unknown* keys. It does **not** reject a flat
  `rm_state`/`rmState` on `ParticipantStatus` or `CaseStatus`, because those
  spellings are declared `AliasChoices` on the field and are therefore
  *interpreted*, not dropped. Removing those aliases is #2288/#2289.
- Persisted rows are still keyed by Python field name (`id_`, `type_`), not the
  wire-facing names ARCH-23-005 asks for. Re-keying was deliberately **not** done
  in #2940 — it would mask the `CaseLedgerEntry` alias-injection bug — and is
  sequenced behind the `WireParsePort` (#2938). See
  [notes/wire-core-boundary.md](wire-core-boundary.md).

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

## A DataLayer Fallback Is a Smell for a Masked Protocol Bug

Reading a protocol-significant field from the DataLayer *as a fallback* — when
that field could have arrived in the received message — is a smell for a masked
bug or race. When a handler tries `event.activity.object_...` and, finding it
absent, falls back to `dl.read(...)`, it usually only works because a prior
delivery happened to store the value; that hidden dependency on delivery order
is a latent race, not a safety net.

`_read_invite_roles()` in
`vultron/core/behaviors/case/nodes/invite_participant.py` (ISSUE-2719) read invite
roles from the DataLayer rather than from the received activity. A protocol field
that is *present in the message* must be read from the message; treating the
DataLayer as a substitute source silently tolerates a message that never carried
it.

**How to apply:**

- Read protocol-significant fields from the received message
  (`event.activity.object_...`) — the authoritative carrier under the Actor
  Knowledge Model.
- A **missing** protocol field is a protocol VIOLATION, not a cue to search the
  store: log it and return an empty/default result. Do not silently DL-fallback.
- DataLayer reads stay correct for **persisted state that cannot travel in the
  message** — the local `VulnerabilityCase` for derived fields, idempotency/dedup
  guards, correlation indexes. The smell is specifically substituting a DL read
  for a field the message should have carried.

This is the same message-primacy principle as the semantic-content rule in
[Activity Read-Back](#activity-read-back-semantic-content-vs-envelope-reconstitution-adr-0035-dl-06)
(DL-06-001/002: core MUST NOT re-read a stored activity to interpret it) and the
message-subject-identity rule in
[notes/wire-core-boundary.md](wire-core-boundary.md).

*Source: ISSUE-2719 — `_read_invite_roles()` DataLayer fallback.*

## Received Activity Artifacts: Inline Sub-Field Snapshots Are Intentional

**Principle.** A received Activity is an **artifact** — the exact wire object
received is worth storing as-is. `_dehydrate_data` in
`vultron/adapters/driven/db_record.py` deliberately does NOT recursively
dehydrate the sub-fields of an inline Activity object. When `Accept` stores an
inline `Offer`, the `Offer`'s own `object_`, `target`, etc. are preserved as a
snapshot of what they contained at receipt time — not collapsed to ID strings.

This is correct behaviour and must not be changed. The rationale has two parts:

1. **Technical**: inline Activities may not have independent DataLayer records
   (e.g., a reconstituted `Offer` in the validate-report path, a
   `CaseLedgerEntry` inside an `Announce` envelope). Collapsing them to a bare
   ID would make rehydration impossible on read-back.

2. **Semantic (more important)**: even where independent records exist, the
   snapshot captures state at receipt time — "when you offered me this case, it
   looked like this." An `Accept(Offer(VulnerabilityCase))` is a contract: it
   records what was offered at the moment of acceptance, not the current state
   of the case. The case will evolve; the contract must not.

**Two copies, not one.** If an actor receives `Offer(Case)` and then extracts
the case to seed a live record in its DataLayer, two distinct things now exist:

- The **artifact** — the stored `Offer` with its frozen `Case` snapshot.
  Immutable in the context of that offer. Read it to answer "what was I
  offered?" Never update it.
- The **live record** — the `VulnerabilityCase` actively maintained by the
  actor. Participants join, states transition, embargo terms change. This copy
  evolves.

These two copies diverge over time **by design**. Do not treat the snapshot as
the current state of the object, and do not write the snapshot back over the
live record when refreshing or re-seeding.

**Why recursive dehydration would be wrong.** If `_dehydrate_data` were
extended to recurse into inline Activity sub-fields, `Accept.object_.object_`
would become a bare ID string pointing to the *current* `VulnerabilityCase` —
losing the at-offer-time snapshot. Even if Activities eventually gain
independent DataLayer records (removing the technical constraint), the semantic
reason alone prohibits recursive dehydration here.

Source: CONCERN-2219. See also `notes/wire-artifact-immutability.md` for the
full design (A/B split, `frozen=True` enforcement, outbound blob pipeline, and
VM-08-002/003 spec requirements).

---

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
- `vultron/adapters/driven/datalayer_sqlite/`
- `vultron/wire/as2/rehydration.py`
- `vultron/wire/as2/vocab/registry.py`

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

## One Actor Id Is One Database

An `actor_id` is a **store name**, not a label on a store. `get_datalayer()`
requires an actor and returns that actor's own store (DL-07-002); there is no
ambient or unscoped singleton to reach for. A BT's store is the store of its
executing actor, reconciled once in `BTBridge._store_for_actor` (BT-05-005), so a
node cannot write to "some other" store by forgetting to use `self.datalayer`.

Two hazards follow, in opposite directions, and both have bitten:

- **Two DataLayers built for the same actor id are the *same* database**
  (DL-07-004). Two scenarios that must not see each other's rows therefore need
  two actor ids — deriving one per test (`f"{ACTOR_ID}/{slug}"`) is enough and
  self-documenting. The loud symptom is the second seed raising
  `ValueError: record with id_=... already exists`.
- **Sharing one store between two logical actors hides a *missing* write**: the
  reader finds the writer's row and the test passes for the wrong reason. This is
  the defect class ISSUE-2238 was about, and it is why several tests were found
  asserting nothing at all. Conversely, do not give one logical actor two ids
  merely to get a fresh database — that reintroduces the masking.

Only the loud hazard was noticeable before per-actor storage, which is why the
silent one accumulated.

`test/conftest.py` carries an autouse `_dispose_actor_stores_between_tests` —
**do not remove it.** It handles the *between-test* case only; both hazards above
occur *within* a single test, where no fixture can help.

References: ADR-0073 and ISSUE-2238 for the decision. Rewritten tests:
`test/core/behaviors/case/test_case_proposal_received_tree.py::TestCreateCaseProposalReceivedBTCaseActorRecords`,
which asserts against each actor's own store rather than against an empty
singleton.

## Declaring a Test's Executing Actor

Because a BT's store follows its executing actor (BT-05-005, above), a test that
seeds one actor's store and runs `execute_with_setup(actor_id=<other>)` reads an
empty one. Declare the executor with `@pytest.mark.executes_as(ACTOR)` —
`bt_scenario` honours it — or build the scenario per actor with
`bt_scenario_factory`. Derive a test's executing actor by looking at
`execute_with_setup(actor_id=…)` and `receiving_actor_id`, never from fixture or
test names.

Source: ISSUE-2238
