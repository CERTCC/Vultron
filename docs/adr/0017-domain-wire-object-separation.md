---
status: accepted
date: 2026-06-03
deciders: Vultron maintainers
consulted: notes/domain-model-separation.md
---

# Domain/Wire Object Separation: Parallel Core Class Hierarchy

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

## Decision Outcome

Chosen option: **B — introduce a `CoreObject` base in `core/models/`,
parallel to `as_Object`**, because it cleanly satisfies the layer-
boundary rule (core never imports wire), keeps wire-layer JSON-LD
concerns (`@context`, AS2 vocabulary registry) out of the domain, and
gives future per-type migrations a stable foundation to inherit from
without duplicating the `id_`/`type_`/`published`/`updated`/`name`
boilerplate that every domain object needs.

### Decision details

1. **Parallel hierarchy.** A new `CoreObject` class lives in
   `vultron/core/models/base.py`. It inherits from the existing
   `VultronObject` (so it transitively carries the AS2-derived fields
   `id_`, `type_`, `name`, `attributed_to`, `published`, `updated`,
   plus the broader set of optional fields that already exist on
   `VultronObject`). It adds the JSON-LD `context_` field
   (validation/serialization alias `@context`), which has no default —
   the wire projection supplies the AS2 namespace at serialization
   time. (`VultronObject` itself remains in place to keep the existing
   `Vultron*` stubs untouched, per issue #724 AC-4.)

   Concrete subclasses register themselves in `CORE_VOCABULARY` via
   `__init_subclass__`. A subclass is registered only when it overrides
   `type_` with a concrete (non-union) annotation, mirroring the
   wire-layer `VOCABULARY` registration rule. The registry key is the
   subclass's `__name__` verbatim — no prefix to strip, because core
   classes have no `as_` prefix.

2. **Core fields hold full objects, not refs.** Domain fields MUST NOT
   use `Object | str | Link | None` unions. The "inline-or-ref"
   polymorphism is a wire-format concern; the wire layer translates
   bare-ID and `Link` forms into full embedded objects at the
   deserialization boundary, and the `DataLayer` hydrates IDs on read.
   The only intentional exception is a small set of cases where the
   core legitimately needs an ID reference for a graph-cycle reason
   — e.g., parent/child case linkage on `VulnerabilityCase`, where
   embedding the parent object would either recurse infinitely or
   prematurely materialize an entire case tree. Such cases MUST be
   called out explicitly at the field site with a comment naming this
   ADR.

3. **Naming convention.** Migrated core types use the canonical CVD
   domain vocabulary without a `Vultron` prefix:

   - `VulnerabilityCase` (not `VultronCase`)
   - `VulnerabilityReport` (not `VultronReport`)
   - `CaseStatus`, `CaseParticipant`, `EmbargoPolicy`,
     `CaseLogEntry`, `VulnerabilityRecord`

   "Wire-style" here means **the canonical Vultron domain vocabulary
   already used in the wire layer's class names**, not "ownership by
   the wire layer." After migration, the wire layer's domain-object
   modules become thin projections that re-export the core types
   (possibly wrapped in an AS2-flavored adapter when JSON-LD-specific
   behavior is needed). The legacy `Vultron*` stubs in
   `vultron/core/models/` (`VultronCase`, `VultronReport`,
   `VultronNote`, etc.) are intentionally left in place by issue #724
   and will be replaced as each type migrates under issue #699.

### Consequences

- Good, because `VultronActivity.object_` can be retyped as a Pydantic
  discriminated union once at least the first few domain types
  migrate, deleting `_STUB_OBJECT_MODEL_MAP` and the dict-recovery
  block in `outbox_handler.py`.
- Good, because core handlers and behavior-tree code stop seeing
  `Object | str | Link | None` shapes; field types match the
  developer's mental model.
- Good, because the registry pattern proven in the wire layer carries
  over without surprises and supports future bulk operations
  (discriminated-union assembly, persistence mapping, schema export).
- Bad, because two base classes (`VultronObject`, `CoreObject`) coexist
  during the migration window, with `CoreObject` inheriting
  `VultronObject` to honor issue #724 AC-2 and avoid disturbing the
  existing stubs. Once #699 completes, `VultronObject` can fold into
  `CoreObject` (or vice versa) in a follow-up cleanup.
- Bad, because the `@context` field now exists on `CoreObject` even
  though its only consumer is the wire layer; the default of `None`
  keeps it inert in core code paths.
- Neutral, because the registry is opt-in: only subclasses that supply
  a concrete `type_` register, so future "abstract" intermediate
  bases will not pollute `CORE_VOCABULARY`.

## Validation

- `test/core/models/test_core_object.py` adds coverage for: `CoreObject`
  subclass registration when `type_` is concrete; non-registration
  when `type_` is omitted or union-typed; registry key equals
  `cls.__name__`; existing `Vultron*` stubs do not appear in
  `CORE_VOCABULARY` (they inherit `VultronObject`, not `CoreObject`);
  and a PEP 563 regression test that exercises `from __future__
  import annotations` to ensure the union-skip check is robust to
  stringified annotations.
- The migration of each domain type into core under issue #699 will
  add a test that constructs the core type, serializes via wire, and
  round-trips back through `model_validate()` with object identity
  preserved.
- The layer-boundary rule (core MUST NOT import wire) is already
  enforced by `test/architecture/test_layer_boundaries.py`.

## More Information

- Issue #724 — Refactor #699 step 1: core base hierarchy + ADR for
  domain/wire object separation (this ADR).
- Issue #699 — Migrate domain objects from
  `wire/as2/vocab/objects/` to `core/models/` and type
  `VultronActivity.object_` as a discriminated union.
- Concern #586 — original layer-boundary inversion report.
- PR #577 — `_STUB_OBJECT_MODEL_MAP` workaround that this design
  eventually deletes.
- `notes/domain-model-separation.md` — full architectural direction,
  including the translation-boundary model
  (Wire DTO → Domain Model → Persistence Model) and the
  domain-events-as-bridge discussion.
- `notes/codebase-structure.md` "Core Object Modules" — related
  file-splitting recommendation.
- ADR-0009 — Hexagonal Architecture (Ports and Adapters), the
  enclosing rule this ADR operationalizes for domain objects.
- ADR-0010 — Standardize Object IDs to URI Form; the ID format that
  makes `DataLayer.hydrate()` viable.
