---
source: NOTES-datalayer-design--read-path-core-objects
timestamp: '2026-09-17T17:19:54.744476+00:00'
title: Read Path MUST Return Core Objects (ADR-0034, DL-05)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) self-marked Implemented (PR #1529); DL-05 end-state met
**Superseded by:** docs/adr/0034-datalayer-returns-core-objects.md; specs/datalayer.yaml DL-05

---

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
