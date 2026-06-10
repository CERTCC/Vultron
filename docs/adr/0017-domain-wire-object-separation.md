---
status: accepted
date: 2026-06-03
deciders: Vultron maintainers
consulted: notes/domain-model-separation.md
amended: >-
  2026-06-05 — Changed decision from Option B to Option D
  (shared-base, two-branch hierarchy); see concern #796.
---

# Domain/Wire Object Separation: Shared-Base, Two-Branch Hierarchy

## Context and Problem Statement

`VulnerabilityCase`, `VulnerabilityReport`, `CaseParticipant`,
`EmbargoPolicy`, `CaseStatus`, `CaseLogEntry`, and `VulnerabilityRecord`
are **domain objects**: they describe the Vultron protocol's state, not
the ActivityStreams 2.0 (AS2) wire format. The codebase, however, was
built wire-first, so these classes currently live under
`vultron/wire/as2/vocab/objects/` and inherit from the AS2 base class
hierarchy (`as_Base` → `as_Object` → ...).

This produces a layer-boundary inversion. The core layer
(`vultron/core/`) is forbidden from importing the wire layer
(`vultron/wire/as2/`); to satisfy that rule, `VultronActivity.object_`
in `vultron/core/models/activity.py` is typed `Any | None`. Round-trips
through `model_dump() → model_validate()` therefore lose typed object
identity: nested domain objects deserialize as plain `dict`s, and
`DataLayer.hydrate()` is silently skipped. PR #577 added an
`_STUB_OBJECT_MODEL_MAP` workaround in `outbox_handler.py` that covers
only `VulnerabilityCase` and requires per-type manual registration.

Wire-format concerns also leak into the domain: AS2 freely models a
nested object as an inline object, a bare ID string, or a `Link`
reference, which forces core fields into `Object | str | Link | None`
unions. Behavior-tree code, persistence code, and use-case handlers all
pay the cost.

Issue #699 tracks the per-type migration. Before any migration can land,
core needs a **parallel base class hierarchy** that mirrors the wire
layer's `as_Base` / `as_Object` shape — without inheriting from it.
This ADR records the decision to introduce that hierarchy, the naming
convention used by the migrated types, and the rule that core fields
hold full objects rather than wire-style references. Issue #724 lands
only the foundation; no per-type migrations occur in the same change.

## Decision Drivers

- Restore the hexagonal boundary: domain logic lives in `core/`, wire
  logic lives in `wire/`. Core MUST NOT import wire.
- Make `VultronActivity.object_` typeable as a Pydantic discriminated
  union so round-trips preserve object identity and `hydrate()` is
  reached without per-type stub maps.
- Avoid leaking AS2 "inline-or-ref" polymorphism into the domain.
- Provide a stable, registered vocabulary the future discriminated
  union and bulk-migration tooling can iterate over.
- Keep the change reversible and small: foundation-only, no behavioral
  change.

## Considered Options

- **A. Re-home domain types under `core/models/`, no shared base.** Each
  migrated type inherits directly from `pydantic.BaseModel`.
- **B. Introduce a `CoreObject` base in `core/models/`, parallel to
  (but not derived from) `as_Object`.** Wire-side classes become thin
  projections that re-export or wrap the core types.
- **C. Move `as_Object` itself into `core/` and re-export from wire.**
  Domain types continue to inherit from a single shared base.
- **D. Make the wire hierarchy inherit from the same lenient shared base
  already used by the core hierarchy (`VultronBase` / `VultronObject`).**
  Both branches share a root in `core/models/base.py`. The core branch
  adds domain validators and required-field constraints; the wire branch
  adds AS2 serialization concerns (`alias_generator=to_camel`, hardcoded
  `@context`). No diamond inheritance at the concrete-type level;
  translation between branches uses Pydantic's `model_validate()`
  round-trip. No `from_core()` / `to_core()` protocol is required.

## Decision Outcome

Chosen option: **D — shared-base, two-branch hierarchy**, superseding the
original Option B chosen when this ADR was first drafted.

> **Amendment note (2026-06-05):** The original decision was Option B
> (parallel independent `CoreObject` hierarchy). Option B was the correct
> first step; its code artifacts (`CoreObject`, `CORE_VOCABULARY`, and the
> migrated domain types from the #699 chain) are fully preserved and become
> the **core branch** under Option D. Concern #796 and the post-merge
> analysis of PR #794 revealed that completely independent hierarchies
> block the `from_core()`/`to_core()` translation protocol defined by
> ARCH-12 and force workarounds (`CoreActor | as_Actor` unions in adapters;
> re-export instead of proper wire types). Option D resolves this by
> connecting both branches at a shared lenient root.

### Decision details

1. **Shared root.** `VultronBase` and `VultronObject` (already in
   `vultron/core/models/base.py`) are the shared root for both
   hierarchies. They define all shared fields with the most lenient
   types (`str | None`, `Any | None`, `datetime | None`). No AS2-specific
   serialization concerns live in the shared root.

2. **Core branch adds domain constraints.** `CoreObject` (and all migrated
   domain types) inherit from `VultronObject`. The core branch narrows
   inherited fields via Pydantic `AfterValidator` annotations (e.g.,
   `NonEmptyString | None`) and enforces domain invariants (required fields,
   URI validation). Core-branch types MUST NOT carry wire-specific concerns.

3. **Wire branch adds AS2 concerns.** `as_Base` inherits from `VultronBase`;
   `as_Object` inherits from `VultronObject`. The wire branch adds
   `alias_generator=to_camel`, the hardcoded `@context` AS2 namespace, and
   lenient field types required by the AS2 vocabulary (`Any | None`).
   Wire-branch types MUST NOT carry domain validators.

4. **No diamond inheritance at concrete-type level.** Core and wire types
   remain in separate branches. Concrete domain types live in the core
   branch only; concrete wire types live in the wire branch only. The
   re-export pattern (ARCH-09-002) is a transitional state, not the
   long-term design: once wire-branch actor types are implemented, the
   re-export is removed.

5. **Translation is `model_validate()`.** Both branches share field names
   and the shared-base field types are compatible with the core branch's
   narrowed types. Converting between a core object and its wire counterpart
   uses `WireType.model_validate(core_obj.model_dump(mode="json"))`. No
   explicit `from_core()` / `to_core()` classmethods are required; ARCH-12
   is superseded by this decision.

6. **`inbox` / `outbox` are URI strings in the domain.** Actor `inbox` and
   `outbox` fields carry endpoint URI strings (`str | None`) in the shared
   base and core branch. AS2 `OrderedCollection` wrapping is a wire-only
   serialization concern. `CoreActorCollection` is transitionally deprecated.

7. **Naming and registry conventions are unchanged.** Core types continue
   to use canonical CVD vocabulary names (no `Vultron` prefix) and register
   in `CORE_VOCABULARY`. Wire types register in `VOCABULARY`. Both
   conventions were established under Option B and carry forward.

8. **Core fields hold full objects, not refs.** This rule from Option B is
   unchanged. Domain fields MUST NOT use `Object | str | Link | None`
   unions. The only intentional exception is graph-cycle linkage (e.g.,
   parent/child `VulnerabilityCase`); such cases MUST include a comment
   naming this ADR.

9. **Implementation note.** The `CoreActor` type as shipped by the #699
   chain carries wire concerns (`alias_generator=to_camel`, hardcoded
   `@context`) because it was migrated before this amendment. Removing
   those concerns and introducing proper wire actor types is tracked by
   the implementation epic following concern #796.

### Consequences

- Good, because ARCH-12's `from_core()` / `to_core()` translation protocol
  is superseded. Translation is simple `model_validate()` for the common
  case, with no per-type stub required.
- Good, because `CoreActor | as_Actor` union annotations in adapter
  functions collapse to `CoreActor` once proper wire actor types are in
  place and `VOCABULARY["Actor"]` is updated to `CoreActor`.
- Good, because `CoreActorCollection` can be removed; `actor.inbox` and
  `actor.outbox` become plain `str | None`, eliminating the most
  structurally irreconcilable field-type conflict that blocked ARCH-12.
- Good, because `VultronActivity.object_` can still be typed as a Pydantic
  discriminated union — the #699 chain's primary goal — since
  `CORE_VOCABULARY` carries all registered core types.
- Bad, because the #699 migration placed wire concerns (`to_camel`,
  `@context`) inside `CoreActor`; removing them requires a follow-up
  implementation pass tracked by the new epic.
- Neutral, because the two base classes (`VultronObject`, `CoreObject`)
  and the registry pattern are unchanged; the additional wire-branch
  inheritance wiring is new but small in surface area.

## Validation

- `test/core/models/test_core_object.py` retains coverage for `CoreObject`
  subclass registration, non-registration for abstract bases, and the
  PEP 563 regression test — all established under Option B.
- Implementation issues from the new epic will add tests verifying:
  - `as_Base.__bases__` includes `VultronBase` (or a subclass thereof).
  - `as_Object.__bases__` includes `VultronObject` (or a subclass thereof).
  - `CoreActor` does not define `alias_generator` or a hardcoded `@context`.
  - `CoreActor.inbox` and `CoreActor.outbox` are annotated `str | None`.
  - A `model_validate()` round-trip from a core actor to a wire actor
    preserves field values for all shared fields.
- The layer-boundary rule (core MUST NOT import wire) continues to be
  enforced by `test/architecture/test_layer_boundaries.py`.

## More Information

- Concern #796 — Architecture clarification for core & wire class hierarchy;
  the driving observation for the amendment from Option B to Option D.
- PR #794 — Migrated Vultron actor types to `core/models/`; post-merge
  review surfaced the 17 field-type conflicts that prompted the amendment.
- Issue #724 — Refactor #699 step 1: core base hierarchy + ADR for
  domain/wire object separation (established Option B).
- Issue #699 — Migrate domain objects from `wire/as2/vocab/objects/` to
  `core/models/` and type `VultronActivity.object_` as a discriminated
  union. (Completed; created the core branch artifacts used by Option D.)
- Concern #586 — original layer-boundary inversion report.
- PR #577 — `_STUB_OBJECT_MODEL_MAP` workaround that the #699 chain deleted.
- `notes/domain-model-separation.md` — full architectural direction,
  including the translation-boundary model
  (Wire DTO → Domain Model → Persistence Model).
- `notes/codebase-structure.md` "Core Object Modules" — related
  file-splitting recommendation.
- ADR-0009 — Hexagonal Architecture (Ports and Adapters), the
  enclosing rule this ADR operationalizes for domain objects.
- ADR-0010 — Standardize Object IDs to URI Form; the ID format that
  makes `DataLayer.hydrate()` viable.
