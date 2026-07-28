---
status: accepted
date: 2026-07-17
deciders: Vultron maintainers
consulted: notes/datalayer-design.md, notes/domain-model-separation.md, ADR-0034, ADR-0017
informed: CERT/CC Vultron contributors
---

# Core Activity Representation and Envelope Reconstitution

## Context and Problem Statement

Vultron is a set of communicating **core** state machines. Each Actor is an
isolated process: it owns a DataLayer of core domain objects, and (per the Actor
Knowledge Model) its knowledge of the world is bounded strictly by what it has
received. No actor can reach into another actor's DataLayer. Wire (AS2) exists
solely as the transport by which one actor's core state informs another's — an
AS2 Activity is an **envelope carrying a core domain fact** across the process
boundary, not a domain object in its own right.

ADR-0017 established that wire is a **projection of core**, and ARCH-09-001
requires core models to be as rich as or richer than their wire counterparts.
The 29 AS2 protocol Activities (`Offer`, `Invite`, `Accept`, `Reject`, …) break
this: they were built wire-first and were never given a core counterpart. For
these types the projection is **inverted** — wire is the only representation,
and is therefore richer than core.

The concrete consequence: when an actor must remember what a message told it
(the case id an `Invite` carried, the recommender an `Offer` named, the report
embedded in a submit `Offer`, the pending embargo proposal for a case), there is
**no core object to hold that fact**, so core reaches back through the DataLayer
and re-reads the stored wire envelope — `dl.read(activity_id)` inside
`vultron/core/`. Concern #1506 audited these sites. ADR-0034 recognised activity
read-back as a boundary violation but explicitly scoped it **out** and deferred
it to a separate concern; this ADR is that concern's decision.

The `dl.read(activity_id)` call in core is a **symptom**. The root cause is a
**missing layer of core domain representation for protocol facts**. A second,
subtler question surfaced during analysis: emitting a reply (e.g. an `Accept`)
requires the full inline **verbatim original** activity in the reply's `object_`
(the Actor Knowledge Model forbids bare URIs), and activity ids are
non-regenerable random `urn:uuid:` values — so the original envelope cannot be
losslessly reconstructed from core state. Does that legitimise reading a stored
activity back?

## Decision Drivers

- Restore "wire is a projection of core" (ADR-0017) and ARCH-09-001: every
  domain fact an actor remembers MUST have a home in core.
- Honour ARCH-03-001 (AS2↔domain mapping happens in exactly one place, the
  semantic extractor) — core MUST NOT re-interpret an activity a second time.
- Honour ARCH-01-002 / DL-05: wire vocabulary types MUST NOT enter core through
  the persistence port.
- Do not regress into cloning each AS2 Activity into a 1:1 core Activity class —
  the generic-event-mirroring-AS2 anti-pattern `notes/domain-model-separation.md`
  warns against.
- Satisfy the Actor Knowledge Model's requirement that replies embed the full
  inline original activity, given that activity ids are not regenerable.
- Keep the migration measurable and regression-proof via the DL-05-004 ratchet.

## Considered Options

- **A. Give protocol facts a core representation; correlate via core entities;
  confine verbatim reconstitution to a wire/adapter seam.** The extractor
  records the domain fact each inbound message carries as core state (a
  transition on an existing core entity or a purpose-built core record) at
  interpretation time. Core reads that core state; correlation between messages
  (Accept→Invite) flows through a core-entity relationship. Verbatim envelope
  reconstitution for replies reads a stored activity back only through a
  wire/adapter-owned seam that treats the payload as opaque.
- **B. Clone each AS2 Activity into a 1:1 core Activity class.** Give every
  protocol message a mirror core type and read that instead. Rejected: this
  duplicates the wire envelope into core rather than modelling the domain fact,
  reproduces AS2-shaped fields (`object_`, `target`, `context`) in core
  vocabulary, and is the exact anti-pattern `notes/domain-model-separation.md`
  cautions against. It relocates the violation without curing it.
- **C. Pure read-relocation / lossless re-projection.** Stop storing activities;
  reconstruct any needed envelope by re-projecting core state through the
  serializer on demand. Rejected: activity ids are random `urn:uuid:` values, so
  re-projection produces a different id and serialization every time — it cannot
  reproduce the verbatim original the Actor Knowledge Model requires for reply
  `object_`. Lossless reconstitution from core state is not achievable.

## Decision Outcome

Chosen option: **A**, because it is the only option that gives protocol facts a
true core home (curing the ARCH-09-001 inversion rather than relocating it,
rejecting B) while still satisfying the Actor Knowledge Model's verbatim-reply
requirement given non-regenerable ids (which C cannot meet).

The decision splits two needs that `dl.read(activity_id)` conflates today:

| Need | Source of truth | Rule |
|---|---|---|
| **Semantic content** — what a message *means* (case id, embargo id, recommender, embedded report) | **Core state** | MUST come from a core entity; core MUST NOT re-read the activity to interpret it (DL-06-001, DL-06-002). |
| **Correlation** — which prior message this one answers | **Core-entity relationship** | MUST resolve through a domain relationship, not a wire re-read (DL-06-003). |
| **Envelope reconstitution** — embedding the verbatim original in a reply's `object_` / `in_reply_to` | **Stored opaque activity payload** | MAY read a stored activity, but only via a wire/adapter-owned seam that never interprets it (DL-06-004). |

### Decision details

1. **Protocol facts get a core representation.** The semantic extractor — the
   single interpretation site (ARCH-03-001) — records each domain fact a
   received message carries as core state at interpretation time, either as a
   state transition on an existing core entity or as a purpose-built core record.
   This is **not** a 1:1 clone of the AS2 Activity: model only the domain fact,
   in domain vocabulary, capturing only what handlers use (DL-06-002).
2. **Core reads facts from core state, never from the wire envelope.** Core code
   MUST NOT call `dl.read(activity_id)` / `dl.list_objects(<activity_type>)` to
   recover semantic content (DL-06-001).
3. **Correlation is a core-entity relationship.** When a message references a
   prior one, core correlates through the core entity the prior message created
   or updated — not by re-reading the referenced activity (DL-06-003).
4. **Verbatim reconstitution is a wire/adapter seam.** Reading a stored activity
   payload back to embed the verbatim original in an outbound reply is permitted,
   but owned by the wire/adapter layer and treated as opaque; core never reads it
   to interpret meaning. Such a seam is **not** counted as a core boundary
   violation under DL-05-004 (DL-06-004). `CaseLedgerEntry.payloadSnapshot` is the
   existing precedent for opaque, write-only activity retention.
5. **The ratchet shrinks to zero.** As each core semantic read is migrated off
   activity read-back, its AS2 Activity type is removed from the DL-05-004
   exemption set; the set MUST reach zero, leaving only the DL-06-004 seam
   (DL-06-005).

The migration itself is out of scope for this decision — this concern's
deliverable is the audit and the implementation issues. The audited sites and
their classification are recorded in `notes/datalayer-design.md`.

### Consequences

- Good, because protocol facts gain a canonical core home, restoring "wire is a
  projection of core" (ADR-0017, ARCH-09-001) and removing the runtime
  `core → wire` dependency (ARCH-01-002).
- Good, because interpretation happens exactly once, at the extractor
  (ARCH-03-001); core stops maintaining a second, drifting reading of the same
  message.
- Good, because the verbatim-reply requirement is met honestly (via retained
  opaque envelopes) instead of via unachievable lossless re-projection.
- Good, because the DL-05-004 ratchet gives the migration a measurable,
  regression-proof target of zero core semantic activity reads.
- Neutral, because activities may still be persisted — as opaque
  audit/ledger/reply-envelope blobs — provided core never interprets them.
- Bad, because the migration is wide (report, embargo, actor/participant
  subsystems) and staged across multiple implementation issues; the exemption
  set shrinks incrementally rather than at once.

## Validation

- The DL-05-004 architecture ratchet asserts no `vultron.wire.as2` vocabulary
  type escapes `dl.read()` / `dl.list_objects()` into `vultron/core/`, with a
  shrink-only exemption set; DL-06-005 ties the exemption set to zero.
- `test/architecture/test_core_no_wire_imports.py` continues to enforce that
  core does not import wire.
- Per-migration PRs remove the migrated Activity type from the exemption set and
  add tests that the domain fact is read from core state.

## More Information

- Concern #1506 — the driving audit (core reads wire AS2 Activities back from the
  DataLayer); parent Epic #1394 (Architecture Hardening).
- ADR-0034 — DataLayer Port Returns Core Domain Objects; recognised activity
  read-back as a tracked separate concern (this one) and established the
  core-object read contract (DL-05) this ADR extends.
- ADR-0017 — Domain/Wire Object Separation; "wire is a projection of core".
- ADR-0009 — Hexagonal Architecture; the enclosing ARCH-01/03/09 rules.
- ADR-0019 — Separate the Case Ledger from the Per-Actor Process Log;
  `payloadSnapshot` precedent for opaque activity retention.
- `notes/datalayer-design.md` § "Read Path MUST Return Core Objects" and
  § "Activity Read-Back: Semantic Content vs. Envelope Reconstitution".
- `notes/domain-model-separation.md` — domain events as the bridge; the
  anti-pattern of cloning AS2 shapes into core.

Generated spec requirements: `datalayer.yaml` DL-06-001 through DL-06-005.
