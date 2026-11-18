---
status: accepted-provisional
date: 2026-11-18
created: 2026-11-18
updated: 2026-11-18
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0099 (the record this one consolidates); ADR-0175;
  ADR-0063, ADR-0074, ADR-0107, ADR-0149; specs/architecture.yaml ARCH-25;
  specs/message-validation.yaml MV-11
informed: []
supersedes:
  - 0099-one-object-model-as2-is-a-serialization.md
partially_supersedes:
  - 0063-wire-rendering-port-for-core-objects.md
  - 0074-wire-activity-artifact-immutability.md
stakeholder_type: [project-contributor]
---

# The Core Classes Are the One Object Model, and AS2 Is Their Serialization

## Context and Problem Statement

The project held three positions in turn on how the domain model relates to the ActivityStreams 2.0 (AS2) wire format.
First every domain type was an AS2 object; then core had a parallel hierarchy of its own (ADR-0017, Option B); then the two hierarchies met at a shared lenient root (ADR-0017, Option D).
The shared root was neither one model nor two, and it produced a steady stream of structural repairs: a wire-to-core normalisation set, branch sentinels, reject-guards for wire spellings, a pairing registry (ADR-0082) and a plan to move the root to a branch-neutral layer.
ADR-0082 had already removed the root's only justification, the per-class `from_core()` / `to_core()` translation.
A measurement of every class with both a core and a wire form found no semantic disagreement between the two: the differences were one side declining to state a type the other stated, AS2's inline-or-IRI reference form, and spelling.

ADR-0099 settled what the object hierarchy is for.
Its details on unknown inbound keys were then rewritten twice in place, and ADR-0175 replaced its rule for a former field name, so the rule as it stands could be read only by laying ADR-0099's amendments and ADR-0175 over its original text.
Its body also carried its migration record and measured counts, which no longer describe the code.

This record states the decision as it stands.
It decides nothing ADR-0099 and ADR-0175 did not.

What is the object model, and how does it meet the wire?

## Decision Drivers

- **Stop the recurring structural repairs.** Each fix was defensible; the sequence was the defect.
- **Keep AS2 replaceable.** A second wire format should cost a serialization module, not a second class family.
- **Keep core idiomatic.** AS2's semantics — activities as verbs, objects as nouns — fit core; its serialization choices — camelCase, `@context`, inline-or-IRI, optional-everything — do not.
- **Keep the two kinds of object distinguishable.** Conflating a wire object with a core object was the defect that motivated the split.
- **Fail loudly.** Silent field loss is the failure mode to eliminate.
- **Be liberal on receive, with a report** (ADR-0086), except where a key is a spelling of something the receiver reads.

## Considered Options

1. **One object model; AS2 is a serialization of it.**
2. **Move the shared root to a branch-neutral layer**, keeping both hierarchies and the machinery that reconciles them.
3. **Two fully independent hierarchies, bridged by an explicit translator.**
4. **Adopt a third-party AS2 hierarchy** as the wire half (#2947).

## Decision Outcome

Chosen option: **"One object model; AS2 is a serialization of it"**, because the measurement shows there is one model, and this option removes the reconciling machinery rather than moving it.

### Decision details

1. **One set of classes, written out two ways.**
   The classes under `vultron/core/models/` are the object model, and no second set of classes models the same concept (ARCH-25-001).
   For delivery over HTTP a core object is written as AS2 by a `by_alias=True` dump, which emits camelCase names and `@context`; AS2 is the HTTP transmission format only (ARCH-25-011).
   For persistence it is written by a plain JSON dump whose only renaming is of the three identity keys, so no other stored field takes its AS2 spelling (ARCH-25-012).
   `@context` comes from the core serializer on the AS2 path, not from the delivery step, so a `by_alias` dump is complete AS2 with no second step to forget.
   The rendering port is the core object's own `by_alias` dump (ARCH-20-002).

2. **Core field names follow Python convention; the AS2 spelling is the alias.**
   A core field has a Python name, and its AS2 spelling is its Pydantic alias; no parallel core-only naming scheme is built (ARCH-25-002).
   The aliases are derived by one alias generator declared on `CoreObject` and inherited, with an explicit alias only where the generator cannot produce the AS2 name (ARCH-25-013).
   A per-class or per-field declaration lets a sibling ship the wrong spelling unseen, so a closed-world test on the projected key set keeps it honest.
   Core code does not type an AS2 spelling (ARCH-25-014).

3. **A domain type has exactly one class.**
   A wire-facing `as_*` name for a domain type is an alias of its core class, not a separate class (ARCH-25-003).
   Message-shape classes name core classes in their slots (ARCH-25-015).
   So a core class that can appear in a message slot must be exactly AS2-representable: every field has an AS2 spelling, and none cannot go on the wire (ARCH-25-016).
   A core class that never appears in a message is not constrained by AS2.
   With one class there is nothing to project, and core does not look for a `to_core()` (ARCH-25-017).

4. **Wire and core share no root.**
   `as_Base` stands on `pydantic.BaseModel` and carries the AS2 envelope fields (ARCH-25-004, ARCH-25-018).
   Core has two roots: a record base carrying identity only, for records that are not AS2 objects, and one object root carrying the AS2 object fields, `@context` and required timestamps (ARCH-25-019).

5. **A status dimension writes itself as its bare value.**
   A dimension object holds one data field, its state, and writes and reads that bare value, so `RmDimension` writes `"START"` (ARCH-25-005).
   The serializer and reader are declared on the dimension class, because a value object states how it writes itself (ARCH-25-020).
   The enclosing field's alias carries the AS2 spelling, so the wire form does not change (ARCH-25-021).

6. **Wire may import the core model, and nothing else of core.**
   The wire layer imports only `vultron/core/models/` and `vultron/core/states/` (ARCH-25-006).
   The rule is an allow-list attached to the importing directory, so moving a file cannot evade it and a new core package is forbidden by default (ARCH-25-022).
   Core imports nothing from wire (ARCH-25-023).
   Hexagonal dependency rules are asymmetric: outer layers depend inward, and the wire layer stays replaceable as a unit (ADR-0009).

7. **Reading is strict on declared fields, and an unknown inbound key is decided at the parse edge.**
   A recognised field whose value violates its type is refused at the edge (ARCH-25-024, ADR-0032).
   An unrecognised key on inbound data is partitioned off by the parse edge before validation, for every object at every depth, a fetched object included, by one rule (ARCH-25-007, MV-11-001).
   The class an object happens to resolve to does not decide the key (ARCH-25-033, MV-11-006).
   - A **near miss** of a declared spelling — the same string after lowercasing and removing every non-alphanumeric character — refuses the whole activity and names both spellings, because the sender meant a field the receiver reads (MV-11-002, ARCH-25-027).
     No edit distance or other similarity measure is used (ARCH-25-028).
     `@id` and `@type` are never declared spellings, so they are refused as near misses of `id` and `type` (MV-11-007).
   - **Any other** unknown key is set aside and reported once at `INFO` with `activity_id`, the sender's `actor_id`, the field path and the key, and the activity proceeds on its declared fields (MV-11-003).
     A former field name is such a key: before 1.0 there is one protocol and one storage version, so no list of former names is kept, and no guard refuses one by name (ADR-0175, MV-11-012).

   A set-aside key is not carried on the parsed object; the received evidence is its only copy (ARCH-25-026, VM-08-002).
   After the parse, nothing on the receive path re-validates from the raw body (MV-11-005).
   `CoreObject` keeps `extra="forbid"` for in-process and stored data, where an unknown key is always a bug; no core class adds an extras field, and a core class never sees an inbound unknown key, because the parse edge is the only door inbound data enters by (ARCH-25-025, MV-11-004).

8. **Every legitimate AS2 field is declared, so an unrecognised key means an unknown one.**
   The AS2 object and activity field sets are declared on the core roots and the wire `as_Object` base, including fields Vultron does not use, such as `bto`, `bcc`, `icon` and `image` (ARCH-25-008).
   A recognised but ignored field is then structurally distinct from an unknown one, and only an unknown key reaches the partition of detail 7.

9. **An object slot holds the whole object, not an ID, once read.**
   `rehydrate()` owns ID-to-object materialisation and resolves a reference through the `DataLayer` it is given (ARCH-25-029).
   Whether an unresolvable reference is deferred or refused is read off the slot's declared type: a slot that admits `str` keeps the IRI, and a slot that admits only a model refuses (ARCH-25-030).
   Nothing fabricates a placeholder, an actor included, for an unresolved reference (ARCH-25-031).
   **This is a prototype shortcut.** It defers data normalisation rather than solving it; a production system would be expected to hold references backed by one store, with join objects where a relationship carries data of its own, and this detail is to be revisited before production (ARCH-25-009).

10. **The AS2 vocabulary and the formal message set stay separate artifacts.**
    AS2 can express more sentences than Vultron needs, and the formal protocol counts some sentences twice, so neither list is a subset of the other; the mapping between them reconciles them (ARCH-25-010, ADR-0083).
    The message-shape classes subclass AS2 verbs and are the AS2 encoding of a message, so they live under `vultron/wire/` (ARCH-25-032).

### Consequences

- Good, because the duplication is gone at its source: no pairing table, no translators, no shared root to keep aligned.
- Good, because replacing AS2 costs one read and write module, not a second class family.
- Good, because conflating a wire object with a core object is structurally impossible for a domain type: there is one class per concept.
- Good, because the wire-to-core boundary is one allow-list test.
- Good, because an inbound unknown key has one disposition wherever it arrives, chosen for inbound data rather than left to class ancestry.
- Bad, because core classes carry AS2 aliases, so the domain model is visibly shaped by AS2. Many core fields already carried one, so the separation given up was never real.
- Bad, because a core class that can appear in a message is constrained by AS2.
- Bad, because a `frozen` envelope does not freeze the mutable core objects nested in it, so the received evidence is kept as the sealed received body instead (ADR-0074, ADR-0149).
- Bad, because a peer that still sends a former field name gets no refusal: its key is set aside and the activity proceeds without it (ADR-0175).
- Neutral, because the AS2 wire form did not change.

### Confirmation

Each detail is restated as requirements in ARCH-25 of `specs/architecture.yaml` and MV-11 of `specs/message-validation.yaml`, each with a verification clause naming its test.
The principal checks:

- `test/architecture/test_hierarchy_invariants.py`: one class per domain type, the two core roots, the derived aliases, and every AS2 property declared on both roots.
- `test/core/models/test_core_object.py` and `test/adapters/driven/test_db_record.py`: the two serializations.
- `test/architecture/test_core_no_as2_spellings.py` and `test/architecture/test_wire_no_core_object_annotations.py`: no AS2 spelling typed in core, and every promoted class exactly AS2-representable.
- `test/wire/as2/vocab/base/test_wire_base_hierarchy.py`: `as_Base` stands on `pydantic.BaseModel`.
- `test/core/models/test_dimension_bare_serialization.py`: the bare-value dimension form and its unchanged wire form.
- `test/architecture/test_wire_core_import_allowlist.py` and `test/architecture/test_core_no_wire_imports.py`: the import rules.
- `test/wire/as2/test_unknown_key_disposition.py`, `test/architecture/test_no_receive_path_reparse.py` and `test/architecture/test_core_extra_forbid.py`: the unknown-key disposition, no re-parse, and the stored-side `forbid`.
- `test/wire/as2/test_rehydration_materialisation.py`: materialisation, refusal and deferral.
- `test/test_message_semantics_mapping.py`: the message set maps onto the semantic registry, not onto AS2 types one for one.

## Pros and Cons of the Options

### One object model; AS2 is a serialization of it

- Good, because it matches the measurement: there is one model.
- Good, because it removes the machinery rather than relocating it.
- Bad, because it was the largest change of the four.

### Move the shared root to a branch-neutral layer

- Good, because it was incremental and already scoped.
- Bad, because it cements a decision whose premise ADR-0082 had removed.
- Bad, because the branch-neutral module could not register into the core type map without a new registration seam.

### Two fully independent hierarchies plus a translator

- Good, because it removes the inheritance entanglement with no ambiguity.
- Bad, because it keeps every duplicate class and adds a translator, while the measurement shows nothing semantic to translate.

### Adopt a third-party AS2 hierarchy

- Good, because it reduces the hand-maintained surface for the pure-AS2 subset.
- Bad, because it adds a foreign root and leaves the duplication, the actual problem, in place.

## More Information

This record supersedes, whole, [ADR-0099](archived/0099-one-object-model-as2-is-a-serialization.md).
Its ten details are details 1 to 10 here, in order, as ARCH-25 already restates them; its amendments to details 1, 2, 7 and 8 are folded into those details.
Its Migration section, its measured counts and its issue dispositions are not carried forward: they recorded how the work landed, and the counts describe the code as it was measured.
Also not carried forward, because each had been overtaken:

- The near-miss rule's "or a retired name": ADR-0175 made a former name an unknown key, set aside like any other.
- The ledger payload snapshot described as a `dict` rebuilt from the parsed graph: the received evidence is the sealed received body (ADR-0107, ADR-0149).
- The statement that ARCH-12-003 and ARCH-20-001 forbid the alias generator, and the annotations on the architecture requirements: those requirements now state the one-object-model direction.
- The "delivery-supplied `@context`": the core serializer emits it (detail 1).

It carries forward ADR-0099's partial supersession of two live records:

- [ADR-0063](0063-wire-rendering-port-for-core-objects.md): rendering core objects behind a driven port stands; its mechanism and its removal of the alias generator from core do not (details 1 and 2).
- [ADR-0074](0074-wire-activity-artifact-immutability.md): a received activity is immutable evidence; its `frozen` mechanism no longer reaches the nested core objects, so the evidence is sealed as text at parse (VM-08-002).

[ADR-0017](archived/0017-domain-wire-object-separation.md) and [ADR-0082](archived/0082-wire-core-boundary-pairing-registry.md), which ADR-0099 retired, stay retired.

Related:

- [ADR-0009](0009-hexagonal-architecture.md): the wire layer is replaceable as a unit.
- [ADR-0032](0032-validate-at-edge-promote-to-core.md): validate at the edge, promote to core.
- [ADR-0036](0036-status-dimension-objects.md): status dimension objects.
- [ADR-0083](0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md): the message set and the AS2 vocabulary are different shapes.
- [ADR-0086](0086-report-every-violation-reject-the-batch.md): report every violation.
- [ADR-0106](0106-versioning-machine-facing-interfaces.md): an extension a peer wants Vultron to read ships through the versioned context document.
- [ADR-0175](0175-before-1-0-one-protocol-and-storage-version-so-a-former-field-name-is-an-unknown-key.md): before 1.0, a former field name is an unknown key.
- #2947 evaluated a third-party AS2 hierarchy and was closed as not planned.

Requirements: `specs/architecture.yaml` ARCH-25; `specs/message-validation.yaml` MV-11.
