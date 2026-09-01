---
status: accepted
date: 2026-08-13
deciders: Vultron maintainers
consulted: Vultron maintainers
informed: Vultron contributors
partially_superseded_by: docs/adr/0081-wire-core-boundary-pairing-registry.md
---

# Normalise Wire → Core at Ingress, and Enforce It Again at the Persistence Boundary

## Context and Problem Statement

`ParticipantStatus` and `CaseParticipant` each exist in two structurally
incompatible shapes. The core types nest their dimensions
(`rm: RmDimension`, `vfd: VfdDimension` — SDO-03-002, ADR-0036); the wire
projections carry them flat (`rm_state`, `vfd_state`). Reading a nested
dimension off a wire-shaped object yields `None`, and every core reader
substituted an initial state for that `None` — silently resetting a
participant's RM ladder (#2232, with #2264 as the symptom).

`Record.from_obj()` was supposed to keep wire objects out of the store, but its
guard was `type_.startswith("as_")` and wire vocabulary `type_` values are
**bare** (`"CaseParticipant"`). Fifteen wire classes therefore shadowed a
`CORE_VOCABULARY` entry and were written into core-typed rows unchallenged.

So the question is not only *how* to normalise, but **where**: a wire-shaped
object can enter the system at an HTTP ingress boundary, and it can reach the
persistence boundary from several call paths. Enforcing in the wrong place
either misses paths or breaks legitimate inbound traffic.

## Decision Drivers

- No wire-shaped row may exist in the DataLayer — that is the invariant #2232
  asks for, and rows outlive whichever code wrote them.
- A wire-shaped object arriving over HTTP is **legitimate inbound data**, not
  corruption. Treating it as an error is a denial of service against the
  protocol.
- A shape mismatch discovered while reading a *stored* row **is** corruption and
  must fail loudly (ARCH-15-001, ARCH-15-002) — the silent degrade is the whole
  defect.
- The received-side behavior tree must not abort because one embedded
  participant is malformed; the HTTP inbox re-queues on exception, so an
  escaping raise becomes an undrainable poison message.
- Enforcement must be verifiable by a test, not by reviewer vigilance: 15 types
  shadow a core type and the count will change.

## Considered Options

- Normalise at wire→core ingress only
- Normalise at the persistence boundary only
- Normalise at ingress, and enforce again at the persistence boundary
- Unify the two shapes into one class

## Decision Outcome

Chosen option: **"Normalise at ingress, and enforce again at the persistence
boundary"**, because the two placements answer different questions and neither
subsumes the other. Ingress projection is what makes the *behaviour* correct —
inbound data is converted where it arrives, so no core reader ever sees a wire
shape and no reader has to degrade. Persistence-boundary normalisation is what
makes the *invariant* hold — it is the single choke point every write passes
through, so it can guarantee the stored row is canonical no matter which ingress
path missed.

Concretely:

- **Ingress (primary).** `_project_to_core_participant()` in
  `vultron/core/use_cases/received/case/_helpers.py` projects each embedded
  participant of a received case snapshot via `to_core()` before anything reads
  it. An unprojectable participant is logged at ERROR and **skipped**, not
  raised: losing one malformed participant is strictly better than losing the
  case.
- **Persistence (backstop).** `_normalize_to_core()` in
  `vultron/adapters/driven/db_record.py` projects the object *and its direct
  children* for every `type_` in `_NORMALIZE_WIRE_TO_CORE`. Children matter
  because a `VulnerabilityCase` row stores `case_participants` inline; one level
  suffices because `to_core()` recurses.
- **Readers stay strict.** `participant_status_rm_state()` and
  `participant_status_vfd_state()` raise `VultronValidationError` on a non-core
  shape. Absence (an empty status list) remains a legitimate `None`.

Rejected for now: unifying the two shapes. It is the right end state — one class
per concept, wire as a pure projection (ADR-0017) — but it is a breaking change
across the AS2 vocabulary and the persisted-row format, and #2232 is a live data
corruption bug. This ADR deliberately buys correctness now without foreclosing
unification later; both enforcement points become redundant, and removable, once
the shapes converge.

### Consequences

- Good, because the DataLayer invariant ("no wire-shaped row") holds regardless
  of which write path is used, including paths not yet written.
- Good, because inbound wire data still works: projection at ingress means
  making readers strict does not break the protocol.
- Good, because a projection failure now raises `VultronValidationError` rather
  than a bare `ValueError`, so it cannot be absorbed by handlers written for
  `crud.create()`'s duplicate-row `ValueError`.
- Bad, because the same projection is expressed in two places, and a reader can
  reasonably wonder which one is authoritative. Mitigated by
  `notes/datalayer-design.md`, which names the persistence boundary as the
  backstop.
- Bad, because `_NORMALIZE_WIRE_TO_CORE` is a hand-maintained list that has to be
  extended by hand for each shadowing type. It covered 7 of the 15 at the time of
  this decision — the other 8 differed only by key spelling, so they were
  misspelled rather than unreadable — and completing the set took issues #2401,
  #2268 and #2402. All fifteen are covered now, behind a grow-only ratchet test.
- Neutral, because per-write child projection costs one `model_fields` scan on
  objects that are already being serialised.

## Validation

- `test/architecture/test_normalize_wire_to_core_ratchet.py` — grow-only ratchet
  on `_NORMALIZE_WIRE_TO_CORE`, plus an exact enumeration of the un-normalised
  shadowing types so a newly added one must be triaged.
- `test/adapters/driven/test_db_record.py` — top-level and nested-child
  normalisation; projection failure raises a non-`ValueError`.
- `test/core/use_cases/received/case/test_helpers.py` — a wire-shaped incoming
  participant against a core-shaped stored one: no raise escapes, the RM
  regression guard still fires, and the persisted row is core-shaped.
- `test/core/models/test_participant_status_shape.py` — both canonical readers
  raise on a wire shape and on a present-but-unusable dimension.

## Pros and Cons of the Options

### Normalise at wire→core ingress only

- Good, because it converts data where it arrives, which is where the type
  information about "this came from the wire" actually exists.
- Good, because it keeps the adapter free of shape-specific knowledge.
- Bad, because it is an open set of call sites. #2232's first fix took this
  reading of the issue, missed the received-case path, and turned every inbound
  `Announce(VulnerabilityCase)` into an aborted behavior tree.
- Bad, because it cannot state an invariant about stored rows.

### Normalise at the persistence boundary only

- Good, because it is one choke point and yields a checkable invariant.
- Bad, because core readers still meet wire-shaped objects *before* the write —
  which is exactly where the RM ladder was being reset.
- Bad, because by the time an error surfaces the useful context (which activity,
  which sender) is gone.

### Normalise at ingress, and enforce again at the persistence boundary

- Good, because behaviour and invariant are both covered, and each placement
  fails safe for the failure mode it owns.
- Neutral, because the redundancy is real but cheap and testable.
- Bad, because two enforcement points must be kept in agreement.

### Unify the two shapes into one class

- Good, because it removes the defect class rather than guarding against it.
- Bad, because it breaks the AS2 wire contract and the persisted-row format at
  once, with no incremental path — not an acceptable shape for a bug fix.

## More Information

**Partially superseded by [ADR-0081](0081-wire-core-boundary-pairing-registry.md).**
That decision takes the unification this ADR named as the right end state and
deferred: with
`extra="forbid"` on the core branch and a declarative core↔wire pairing registry,
the *second* of the two enforcement points chosen here stops being needed. The
persistence-boundary backstop — `_normalize_to_core()`,
`_NORMALIZE_WIRE_TO_CORE`, and the grow-only ratchet — is deleted, because the
invariant it maintains by hand becomes a property of the type system. The
ingress placement stands: inbound wire data is still normalised where it
arrives, and only the mechanism changes, from a direct `to_core()` call to a
`WireParsePort` call. "Readers stay strict" stands unchanged. That is why this
ADR keeps `status: accepted` rather than being retired — the decision a reader
comes here for is still in force, and it remains authoritative for the code as it
stands.

Related: issue #2232 (the shape duality), issue #2264 (initial-state
substitution sites), issue #2268 (migrating the remaining shadowing types).
Related ADRs: ADR-0017 (wire is a projection of core), ADR-0034 (`dl.read()`
returns core objects — this is its write-side counterpart), ADR-0036
(dimension objects on `ParticipantStatus`).

Generated spec requirements: none new — this decision implements existing
`specs/architecture.yaml` ARCH-15-001, ARCH-15-002 and is the write-side
counterpart to `specs/datalayer.yaml` DL-05-001 through DL-05-004.
