---
title: "Wire/Core Boundary — Imports, Union Safety, extra=forbid, Unknown Keys"
status: active
kind: guidance
tags: [wire, core, boundary, vocabulary, pydantic, validation]
description: >
  Rules for the wire/core boundary under one object model (ADR-0099): which
  direction may import which, wire-only type resolution, union-safe validators,
  blank IRI branches, the extra="forbid" contract with its two invariants, and the
  inbound unknown-key rule (MV-11), decided at the parse edge, not by class
  ancestry.
related_specs:
  - specs/architecture.yaml (ARCH-01-001, ARCH-12-003, ARCH-20-008, ARCH-21-002,
    ARCH-22-001, ARCH-22-003, ARCH-23-005, ARCH-23-006, ARCH-25-002 through
    ARCH-25-008)
  - specs/case-management.yaml (CM-11-013, CM-31-003)
  - specs/code-style.yaml (CS-08-001, CS-14-001)
  - specs/error-handling.yaml (EH-07-001, EH-07-003)
  - specs/message-validation.yaml (MV-01-001, MV-02-002, MV-04-003, MV-11-001
    through MV-11-005)
  - specs/vocabulary-model.yaml (VM-06-008)
related_notes:
  - notes/vocabulary-registry.md
  - notes/core-wire-rendering-port.md
  - notes/datalayer-design.md
  - notes/activity-factories.md
  - notes/domain-validation.md
  - notes/status-dimension-objects.md
  - notes/case-joining.md
  - notes/selective-disclosure.md
relevant_packages:
  - vultron/core/models
  - vultron/wire/as2/vocab
  - vultron/adapters/driven
---

# Wire/Core Boundary

One object model (ADR-0099): a paired domain type is a core class that is also
its own AS2 wire form. These rules keep the two branches from leaking into each
other.

## Domain Vocabulary vs. Wire Vocabulary

Keep the wire representation and the domain intent separate, so the translation
point is explicit and neither layer couples to the other's names:

- A domain object MUST NOT inherit from an ActivityStreams base type; AS2
  serialization goes through the rendering port (CM-08-002, ARCH-20-001).
- Wire payload classes carry the `Activity` suffix and domain event classes the
  `Event` suffix (CS-10-002); domain class names use CVD vocabulary
  (CS-12-001).
- Core event and use-case fields use domain names (`report_id`, `case_id`), not
  AS2 roles (`object_id`, `target_id`). The extractor's `ActivityPattern`
  definitions are the one place that maps AS2 fields to semantic roles; do not
  scatter AS2 field handling across use cases.

## Import Direction

| Rule | Direction | How it is met |
|---|---|---|
| ARCH-01-001 | core MUST NOT import wire | rendering through `WireRenderPort` (ADR-0063); parsing through `rehydrate()` (VM-06-007) |
| ARCH-22-001 | wire MAY import only `core/models/` and `core/states/` | allow-list, `test/architecture/test_wire_core_import_allowlist.py` |

Duck-typing a wire capability from core (`getattr(obj, "to_core", None)`) does not
satisfy ARCH-01-001; it only hides the import from the ratchet.

**Never write a goal test for an unreachable state** (ARCH-22-003). A goal that
other MUSTs make impossible invites an implementer to break a MUST to pass it.
Before adding a convergence target, check that no requirement contradicts it; a
clean boundary needs an invariant test, not a target.

### ARCH-12-010 is a trap for wire-side callers

Resolving an inline object's `type` inside a wire tree MUST consider wire-branch
classes only (MV-04-003, VM-06-008). A hit in the core type map is a coincidence
of naming, not a wire counterpart: it places a core class in a wire slot that the
parent field then rejects, degrading the object to a bare `as_Link` (ISSUE-3217).

- "Wire-branch" means *held by the wire registry*: an `as_Base` subclass or a
  class registered in `WIRE_TYPE_MAP`. Not `as_Base` ancestry: the canonical
  `VulnerabilityCase` is a core class registered as its own wire form.
- `find_in_vocabulary()` is wire-only by default; the core fallback is opt-in via
  `include_core=True`. Only the persistence read paths opt in, each saying why at
  the call. Details: [vocabulary-registry](vocabulary-registry.md).
- The parent field annotation is the authority for placing a core object in a
  wire tree, never a name lookup.

## Validators Inside a Union Raise `ValueError`

`as_ObjectRef` is `ActivityStreamRef[as_Object] | CoreObject | None` on purpose
(ADR-0099). A validator reachable inside a union MUST raise a `ValueError`
subclass: anything else escapes the union instead of failing the branch, so
Pydantic never tries the next one. `VultronValidationError` inherits `ValueError`
for this reason; `test_core_guard_inside_wire_union_fails_the_branch` holds it.

Widen a union consistently across every slot that can carry the value. Widening
some slots (`actor`, `object`) but not others (`target`, `origin`, `instrument`)
lets a promoted class escape its declared union, and suppressing the resulting
type errors with `# type: ignore` hides a protocol break from mypy and pyright.
Core classes in wire slots MUST be exactly AS2-representable (ARCH-23-006,
`test/architecture/test_wire_no_core_object_annotations.py`).

### The IRI branch is `NonEmptyString`

`as_Object | as_Link | str` is AS2, not a kludge: a property may hold an embedded
object or an IRI. The `str` branch is `NonEmptyString` (CS-08-001, #3876), so a
blank IRI is refused inbound.

Inside a union Pydantic keeps the `Annotated` wrapper. Code that classifies a
branch with `is str` or by set equality MUST call `strip_annotated()`
(`vultron/core/models/_helpers.py`) first; otherwise it sees no string branch, the
dehydration field set comes out empty, and VM-06-007 refuses a reference it should
defer. Ratchets: `test/architecture/test_wire_reference_fields_reject_blank.py`,
`test_core_reference_fields_reject_blank.py`.

The rule reaches only slots whose annotation spells a string branch. The
`Any | None` AS2 properties on `as_Object` (`to`, `cc`, `attributedTo`,
`inReplyTo`, `context`, `url`, …) still admit a blank inbound, and neither ratchet
sees a string leaf in `Any` (#3894).

## `extra="forbid"` Is the Boundary Contract

`CoreObject` sets `extra="forbid"` (ARCH-12-003): an **unknown** key on a core type
raises instead of being dropped. Pydantic's default `extra="ignore"` would silently
reset the field, losing state without an error (#2232).

`forbid` rejects only keys matching no field. Declared spellings are read:

- camelCase aliases from `alias_generator=to_camel` on `CoreObject` (ARCH-25-002);
- `AliasChoices` on dimension fields (a flat `rm_state`/`rmState` on
  `ParticipantStatus`, `em_state` on `CaseStatus`), which are interpreted, not
  dropped.

A wire-shaped row persisted anyway is projected to core on read
(`hydration.project_wire_row_to_core`). Deliberate snapshot reconstruction in core
goes through `project_wire_snapshot_to_core`, the one seam ARCH-20-008 names.

Two invariants keep `forbid` self-consistent, both validators on `CoreObject`:

- **Strip a matching computed field; refuse a contradicted one**
  (`_check_computed_field_inputs`, ARCH-23-005). A `@computed_field`
  (`VulnerabilityCase.activeParticipants`, CM-31-003) appears in the `by_alias`
  dump but is not settable. Each supplied spelling is checked on its own against
  the derived value; a mismatch raises `VultronProtocolViolationError` with one
  `Violation` per spelling (EH-07-003). Dropping it unconditionally would silently
  erase a peer's contradicting claim. The persistence dump omits computed fields,
  so a stored row cannot contradict a later change to the derivation; an object
  that cannot derive one exactly leaves it out of the `by_alias` dump too. A
  self-contradictory stored row reads back as `None` with a WARNING naming the row.
- **Never leave an alias key beside its field-name twin**
  (`_drop_alias_shadowed_field_names`). The base de-dup validator drops the
  field-name twin; alias wins.

Ratchet: `test/architecture/test_core_extra_forbid.py` (no exemption list).

### The `id_` Failures Are an Alias-Injection Bug, Not a Field-Name Bug

A `mode="before"` validator that derives a field writes it under the alias
(`_set_id_from_case` writes `data["id"]`), and
`CoreObject._drop_alias_shadowed_field_names` then drops the field-name twin
(`id_`) in one place. Do not guard each derivation site yourself, and do not
make the drop raise when the two values differ.

Reason: `CoreRecord` validates by name *and* by alias, so `id` and `id_` are both
sanctioned inputs, and under `forbid` an un-consumed twin is an unknown key. The
alias must win: a derived id (`{case_id}/log/{log_index}`, or a minted urn) is
meant to supersede a caller-supplied `id_`, and raising on disagreement breaks
those paths. Do not re-key persistence to hide the rejection either.

## Inbound Unknown Keys Are Decided at the Parse Edge, Not by Class Ancestry (#3900)

`extra="forbid"` answers *did this process build or store an object with a key it
does not know?* That is always a bug. It is not a decision about a peer's
property: under one object model an inline domain object is a core class, so
ancestry alone would refuse a key on a `VulnerabilityCase` but silently drop the
same key on a wire `Note`. The parser is the inbound wire-to-core seam, so the
disposition is stated once there (MV-11, ARCH-25-007/008):

1. Partition the arriving keys against the resolved class's declared spellings:
   field names, generated camelCase aliases, explicit validation aliases,
   `@context` (MV-11-001).
2. A **near miss** (same string after lowercasing and removing non-alphanumerics,
   or a retired name) **refuses** the whole activity, naming both spellings
   (MV-11-002). Nothing fuzzier: AS2 has too many short names one character apart.
   A snake_case field name is a declared spelling, not a near miss (CS-14-001).
3. Any **other** unknown key is **set aside and reported** at INFO with
   `activity_id`, sender `actor_id`, field path and key; the activity proceeds
   (MV-11-003). Never carry the key on the object: it would leak into the stored
   form, which `forbid` refuses.
4. **Core `forbid` is unchanged** (MV-11-004). The retired-name list lives on the
   wire side (`unknown_keys.RETIRED_NAMES`), consulted only at the parse edge; no
   core guard names a retired key.
5. **Never re-validate from the raw body after parse** (MV-11-005). Set-aside keys
   would reappear on a core class and the wrong type would be stored. Ingress
   storage persists the parsed object.

**`@id` and `@type` are near misses by design** (CONCERN-3958). AS2 spells them
`id` and `type`: the normative context aliases them and AS2 Core § 2.1 requires
the compacted form, so a peer sending `@id`/`@type` sent a non-conforming document
(MV-01-001) and meant the fields Vultron reads. `@context` is the only JSON-LD
keyword that is a declared spelling. Never add `validation_alias="@id"` (or
`"@type"`) to any root (`as_Base`, `as_VultronObject`, `CoreRecord`,
`CoreObject`): that makes Vultron a partial JSON-LD processor with no principled
place to stop.

The partition is `vultron/wire/as2/unknown_keys.py`, called by `parse_activity`
after the received evidence is sealed and before anything validates:

- **An untyped dict** (or one with an unresolved `type`) is judged by the class
  its parent field validates it into, reading through unions, `Annotated` and
  sequences. Several model classes: the union of their spellings. A field that
  also admits `Any` or plain `dict`: no class decides and the dict is carried
  unexamined (its typed children are still partitioned).
- **The case stub** is chosen by its `type`, `VulnerabilityCaseStub` (CM-11-013),
  never by key-set guessing.
- **One refusal names every near miss** at every depth, with dotted paths
  (EH-07-001).
- **A body nested past the recursion limit** is refused as a schema fault
  (`VultronParseValidationError`, MV-02-002); a bare `RecursionError` would draw a
  500.

Ratchets: `test/wire/as2/test_unknown_key_disposition.py` (position matrix, the
`@id`/`@type` keyword guard, and `test_no_core_module_names_a_retired_key`), and
`test/architecture/test_no_receive_path_reparse.py`.
