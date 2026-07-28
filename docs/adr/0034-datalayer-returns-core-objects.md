---
status: accepted
date: 2026-07-17
deciders: Vultron maintainers
consulted: notes/datalayer-design.md, notes/domain-model-separation.md
informed: CERT/CC Vultron contributors
---

# DataLayer Port Returns Core Domain Objects

## Context and Problem Statement

The SQLite DataLayer adapter reconstructs persisted objects through the wire
vocabulary registry (`find_in_vocabulary()` in
`vultron/adapters/driven/db_record.py`). As a result, `dl.read()` and
`dl.list_objects()` return **wire-layer** types (e.g. `as_VulnerabilityCase`
from `vultron/wire/as2/vocab/objects/`) rather than **core** domain types
(e.g. `VulnerabilityCase` from `vultron/core/models/`).

Core BT nodes and use cases call `dl.read()` and operate on the result. To
avoid a compile-time `core → wire` import (forbidden by ARCH-01-001), core
depends on structural duck-typing Protocols and `TypeGuard` helpers in
`vultron/core/models/protocols.py` (`CaseModel`, `is_case_model()`, etc.).
These let core call methods on wire objects at runtime without importing the
wire classes. The boundary "works" only because wire and core types share
field names and the same `type_` string value.

This produces three problems:

1. **Core validators never run on stored data.** A wire object satisfies core
   call sites by structural coincidence; core's domain invariants are never
   enforced on DataLayer-sourced data.
2. **The Protocols evade rather than honour ARCH-01-001.** They hide a runtime
   `core → wire` dependency from static analysis; mypy/pyright pass while core
   operates on wire objects.
3. **The seam is fragile.** After ADR-0017 / issue #1387 renamed wire classes
   to the `as_` prefix (`as_VulnerabilityCase`), the classes are now genuinely
   distinct — but the runtime boundary violation remains, held together only by
   the shared `type_` string and field names.

It was also unclear where wire↔core translation belongs. This ADR records that
decision. Source concern: #1496 (parent Epic #1394).

## Decision Drivers

- Restore the hexagonal boundary: core functions MUST accept and return domain
  types only (ARCH-01-002); core MUST NOT import wire (ARCH-01-001).
- Keep the wire vocabulary registry a wire-layer concern (DL-03-002); the
  DataLayer must not depend on it to reconstruct core objects.
- Prefer a translation boundary that is enforced by types and a ratchet, not by
  structural coincidence.
- Keep the change reversible in stages and reviewable (the core-side cleanup
  touches ~45 files).

## Considered Options

- **A. Adapter reconstructs and returns core objects natively.** The DataLayer
  read path reconstructs persisted domain entities via the core vocabulary
  registry (`CORE_VOCABULARY`). `dl.read()` / `dl.list_objects()` return core
  types. Wire types never enter core. The adapter may still use wire types
  internally, but the port contract is a core object.
- **B. Use cases convert wire → core at each boundary.** DataLayer keeps
  returning wire objects; each core site calls `model_validate` to convert.
  Rejected: scatters conversion across ~45+ sites and is explicitly prohibited
  by DL-01-004 (no `model_validate` on `dl.read()` results in core).
- **C. Physically split into a wire-owned DataLayer and a core-owned
  DataLayer.** Two persistence scopes. Rejected for this decision: changes
  persistence topology and per-actor isolation (ADR-0012); far larger than the
  concern requires. Left as possible future work.

## Decision Outcome

Chosen option: **A — the adapter reconstructs and returns core objects
natively**, because it is the only option that satisfies ARCH-01-002 without
scattering conversion logic (rejecting B) and without re-architecting
persistence topology (rejecting C).

### Decision details

1. **Port contract is a core object.** For every persisted `type_` that has a
   registered core counterpart, `dl.read(id)` and `dl.list_objects(type_key)`
   return an instance of the core `vultron/core/models` class, reconstructed via
   `CORE_VOCABULARY` (DL-05-001).
2. **The adapter owns wire↔core translation** and maintains its own
   `type_`→core-class mapping independent of the wire `VOCABULARY` registry
   (DL-05-002, DL-03-002). Whether the adapter uses wire types as intermediate
   values internally is an implementation detail hidden behind the port.
3. **The duck-typing Protocols are removed.** Once reads return core objects,
   core depends on concrete core classes (real `isinstance` narrowing); the
   workaround Protocols and `TypeGuard` helpers in
   `vultron/core/models/protocols.py` are deleted (DL-05-003).
4. **AS2 Activities are the recognised exception.** Persisted AS2 Activity types
   (the protocol message types in `vultron/wire/as2/vocab/activities/`) have no
   core counterpart, so they cannot be returned as core objects. Core code that
   reads stored wire Activities back from the DataLayer (e.g. reading a stored
   `as_Offer`) is itself a boundary violation, but migrating it out of core is
   **out of scope for this decision** and tracked as a separate concern. Until
   then, the ratchet exemption set (DL-05-004) enumerates these types explicitly
   so it can only shrink.
5. **A ratchet test enforces the contract** (DL-05-004): no `vultron.wire.as2`
   vocabulary type may be returned from `dl.read()` / `dl.list_objects()` into
   `vultron/core/`, except the enumerated Activity exemptions.

### Consequences

- Good, because core validators run on DataLayer-sourced data and the
  wire→core runtime dependency disappears (ARCH-01-001, ARCH-01-002).
- Good, because the DataLayer stops depending on the wire vocabulary registry to
  reconstruct core objects, so the wire layer can evolve independently
  (DL-03-002).
- Good, because ~70 files of duck-typing scaffolding collapse to concrete-type
  usage, restoring static-analysis visibility of the boundary.
- Neutral, because the adapter may retain wire types internally; only the port
  contract changes.
- Bad, because the core-side cleanup is wide (~45 files using guards, ~25 using
  Protocol hints) and is staged across multiple implementation issues.
- Bad, because Activity read-back from core remains a known, tracked violation
  until a follow-on concern migrates it.

## Validation

- An architecture ratchet test asserts no `vultron.wire.as2` vocabulary type
  escapes `dl.read()` / `dl.list_objects()` into `vultron/core/`, with an
  enumerated (shrink-only) exemption set for AS2 Activity types (DL-05-004).
- `test/architecture/test_core_no_wire_imports.py` continues to enforce that
  core does not import wire.
- Existing DataLayer round-trip tests confirm that a saved core object reads
  back as the same core type.

## More Information

- Concern #1496 — the driving report (DataLayer returns wire objects to core).
- Epic #1394 — Architecture Hardening; parent of the implementation work.
- ADR-0017 — Domain/Wire Object Separation (shared-base, two-branch hierarchy);
  established the distinct core and wire class hierarchies this ADR relies on.
- ADR-0009 — Hexagonal Architecture; the enclosing rule (ARCH-01-001,
  ARCH-01-002) this ADR operationalizes for the persistence port.
- ADR-0012 — Per-Actor DataLayer Isolation; relevant to the rejected Option C.
- Generated spec requirements: `datalayer.yaml` DL-05-001 through DL-05-004.
- `notes/datalayer-design.md` § "Vocabulary Registry Entanglement Across Wire,
  Core, and DataLayer" — the analysis this decision resolves.
