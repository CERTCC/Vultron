---
title: "Vocabulary Registry — Design and Migration Notes"
status: active
tags: [vocabulary, registry, wire, as2, deserialization, migration]
description: >
  Design decisions and migration path for the AS2 vocabulary registry
  refactor: auto-registration via __init_subclass__, flat dict, VocabNamespace
  enum, fail-fast on unknown types, and dynamic discovery. Operating rules
  live in vultron/wire/as2/vocab/AGENTS.md.
related_specs:
  - specs/vocabulary-model.yaml
  - specs/architecture.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/wire-core-boundary.md
relevant_packages:
  - vultron/wire/as2/vocab
---

# Vocabulary Registry — Design and Migration Notes

Operating rules summary: `vultron/wire/as2/vocab/AGENTS.md`.
Specs: `specs/vocabulary-model.yaml` (VM-01 through VM-03).

## Problem Statement

The original registry populated itself as a side-effect of class
decorator application:

```python
@activitystreams_object  # writes to VOCABULARY.objects at import time
class VulnerabilityCase(VultronObject): ...
```

This created two fragility points:

1. **Population fragility** — if a vocab module is never imported by any
   application code path, its classes never appear in the registry.
   Deserialization silently fails.
2. **Developer overhead** — every new vocabulary class required the
   developer to add both the decorator and an `__init__.py` import.

## Design Decisions

### 1. Auto-registration via `__init_subclass__`

Registration lives in `as_Base.__init_subclass__`. Every new subclass of
`as_Base` that narrows `type_` to a `Literal[...]` annotation is
automatically registered at class-definition time — no decorator needed.

`__init_subclass__` is explicit in the class hierarchy, deterministic,
and zero-overhead for new classes.

**Alternative rejected**: dynamic-discovery-only (auto-import all sibling
modules from `__init__.py`). Dynamic discovery is retained as a startup
guarantee, but not as the primary mechanism.

### 2. Concrete vs. abstract class detection

Use the `type_` field annotation as the heuristic. A class is treated as
concrete (and registered) if its `type_` annotation is `Literal[...]`.
Abstract/intermediate bases (for example, `as_Object`, `as_Activity`,
`VultronObject`, `as_Actor`) leave `type_` typed as `str | None` and are
skipped.

This avoids boilerplate on abstract classes and matches the existing
pattern where concrete classes narrow `type_` as part of VM-03-002.

### 3. Flat registry dict

Replace the three-sub-dict `Vocabulary(BaseModel)` with a single flat
`dict[str, type[as_Base]]` module-level singleton.

No name collisions exist across objects/activities/links in the current
vocabulary. The `item_type` filter in `find_in_vocabulary()` is
vestigial; all callers use the plain `find_in_vocabulary(name)` form.

### 4. `VocabNamespace` as metadata, not key discriminator

Introduce a `VocabNamespace` enum (`AS`, `VULTRON`) in
`vultron/wire/as2/vocab/base/enums.py`. Each `as_Base` subclass carries a
`_vocab_ns: ClassVar[VocabNamespace]` attribute (default:
`VocabNamespace.AS`). `VultronObject` overrides it to
`VocabNamespace.VULTRON`.

Namespace is **not** part of the dict key — the type name alone is the
key. Namespace remains introspectable on the class for debugging and
possible future filtering.

Most callers of `find_in_vocabulary()` have only a type name string from
the wire `"type"` field. Including namespace in the key would force
callers to know it first, defeating the simplicity of the registry.

### 5. Fail-fast on unknown types

`find_in_vocabulary()` MUST raise `KeyError` when the requested type name
is not in the registry.

A missing type indicates a registration gap that must be fixed before
deployment (VM-06-005). Silent `None` returns allow corrupt
deserialization to proceed undetected.

**Migration note**: callers that previously used `if vocab_cls is not
None` must preserve skip-on-unknown behavior with `try/except KeyError`,
not a `None` check.

### 6. Dynamic discovery as startup guarantee

`vocab/objects/__init__.py` and `vocab/activities/__init__.py` each use
`pkgutil.iter_modules` plus `importlib.import_module` to import all
sibling modules at package import time.

`__init_subclass__` only fires when a class is defined. If a vocab module
is never imported, its classes are never defined and never registered.
Dynamic discovery gives one startup guarantee that all vocab modules are
loaded without requiring each application path to import them manually.

---

## CORE_TYPE_MAP and the ARCH-12-003 Fix

(ISSUE-1992, 2026-08-19)

ARCH-12-003 forbids core-branch types from appearing in the wire `VOCABULARY`
dict. Before this fix, six core types (`VultronOfferRecord`,
`VultronPendingCaseInbox`, `PendingCreateCaseActivity`,
`VultronReplicationState`, `VultronReportCaseLink`, `CoreActor`) were
explicitly assigned to `VOCABULARY` keys in their wire-side re-export modules.

The fix:

1. **`CORE_TYPE_MAP`** (`vultron/core/models/registry.py`) — a new dict
   separate from `VOCABULARY` and `CORE_VOCABULARY`. Auto-populated by
   `VultronObject.__init_subclass__` (for concrete `Literal[...]` `type_`
   annotations) and by `CoreObject.__init_subclass__` (for no-`type_`
   subclasses that use `_set_type_from_class_name`).

2. **`find_in_vocabulary()` fallback** — after checking `VOCABULARY`, the
   function calls `find_in_core_type_map()` before raising `KeyError`.
   This means callers (deserialization, discriminated-union construction) can
   look up core types by name without those types polluting the wire registry.

3. **Wire re-export modules** (`offer_record.py`, etc.) no longer write to
   `VOCABULARY`. They import and re-export the core class unchanged.

**Why `VultronObject`, not `CoreObject`**: five of the six affected types
inherit `VultronObject` directly (not through `CoreObject`), so the hook must
live on the shared root. See
`plan/incoming/learnings/20260819-core-type-map-hook-on-vultronobject-not-coreobject.md`.

**Wire-branch guard** (issue #2416): `as_Object` (the wire-branch root)
overrides `_is_core_branch: ClassVar[bool] = False`. All wire subclasses
inherit this value; `VultronObject.__init_subclass__` checks
`cls._is_core_branch` at entry and returns immediately for any wire-branch
type. Confirmed by `test_no_wire_types_in_core_type_map` in
`test/architecture/test_hierarchy_invariants.py`.

---

## Vocabulary Override Preservation

(ISSUE-801, 2026-06-09)

When overriding actor-type keys in `VOCABULARY` from a Vultron-specific
actor module (e.g., `vultron_actor.py`), overriding **all** actor keys can
leave the base-actors-module (`vultron.wire.as2.vocab.base.objects.actors`)
with zero registered concrete types, tripping the registry-completeness
invariant.

**Rule**: Keep at least one base-actors-module registration. Override only
the concrete keys that need Vultron-specific subclasses (e.g., `Person`,
`Organization`, `Service`), while retaining the generic `Actor → as_Actor`
mapping in the base module.

```python
# base/objects/actors.py — keep at least this registration
VOCABULARY["Actor"] = as_Actor  # ← must stay (and is the correct state as of ISSUE-1992)

# vultron_actor.py — override specific concrete types only
VOCABULARY["Person"] = VultronPerson
VOCABULARY["Organization"] = VultronOrganization
```

**Why**: The registry-completeness test checks that every module under
`vocab/base/objects/` contributes at least one concrete registration.
A module with zero registrations indicates a structural gap (all
registrations were moved elsewhere) and causes the invariant check to fail.

**Current state (post ISSUE-1992)**: `VOCABULARY["Actor"]` correctly maps to
`as_Actor`. The earlier `CoreActor` assignment was removed as an ARCH-12-003
violation — `CoreActor` is a core-layer type and must not appear in the wire
`VOCABULARY`. It is now reachable via `find_in_vocabulary("CoreActor")` through
the `CORE_TYPE_MAP` fallback.

---

## Superseded Direction: Pairing Registry (ADR-0082)

The design below describes the registry as it stands. **ADR-0082 changes its
foundation**, so read this section first:

- The registry key is derived from the class name
  (`cls.__name__.removeprefix("as_")`), *not* from the AS2 `type` value. VM-01-004
  used to claim otherwise; it was only accidentally true and already false for
  the five actor types, which auto-register under `VultronPerson` etc. and are
  *also* explicitly assigned to `Person` etc.
- Because `VOCABULARY` and `CORE_VOCABULARY` share bare-name keys, wire classes
  shadow their core counterparts. **ARCH-23-002 owns this fact**, and its
  verification test (`set(VOCABULARY) & set(CORE_VOCABULARY) == set()`, after
  forcing full registration) is the live check — do not restate a count here,
  because a count in prose drifts the moment a key is renamed. That collision is
  currently **load-bearing**:
  `As2WireRenderAdapter.render()` resolves a core class to its wire counterpart
  with `VOCABULARY.get(type(obj).__name__)`.
- ADR-0082 introduces a declarative core↔wire **pairing registry** as the single
  authoritative statement of that correspondence (ARCH-23-001), which frees the
  two registries to use disjoint keys (ARCH-23-002) and retires
  `_NORMALIZE_WIRE_TO_CORE`, `_WIRE_ACTOR_TO_CORE`, and the name-collision
  lookup together.

Design rationale: [notes/wire-core-boundary.md](wire-core-boundary.md).

## StorableRecord Normalization Gate (`_NORMALIZE_WIRE_TO_CORE`)

(ISSUE-2283, 2026-08-17)

`_storable_to_record` in `vultron/adapters/driven/datalayer_sqlite/crud.py`
applies a `to_obj()` → `from_obj()` round-trip to convert stored
`StorableRecord` data back to its domain shape. This round-trip MUST be
gated on `record.type_ in _NORMALIZE_WIRE_TO_CORE`.

**Why**: Applying the round-trip to ALL types causes silent field loss for
subtype-specific fields. For example, storing a `VultronPerson` via
`StorableRecord(type_="Actor", data_=...)` and round-tripping through
`find_in_vocabulary("Actor")` → `as_Actor.model_validate()` drops all
`VultronPerson`-specific fields (e.g. `embargo_policy`) because the base
`as_Actor` class ignores unknown subtype fields.

**Rule**: `_NORMALIZE_WIRE_TO_CORE` is the exact set of types where core
and wire shapes are structurally incompatible (currently `CaseParticipant`
and `ParticipantStatus`). For all other types, return the verbatim `Record`
directly — either they have no vocabulary entry or their wire vocabulary
class is a faithful supertype of the stored data.

**When adding a new type to `_NORMALIZE_WIRE_TO_CORE`:**

1. The normalization round-trip is applied automatically — no further
   changes to `crud.py` required.
2. If the type is not registered in the wire vocabulary, the
   `except (ValueError, KeyError)` fallback silently skips normalization.
   Add a test to catch this when adding a new type to the set.

<!-- Source: ISSUE-2283 -->

## Related Files

- `specs/vocabulary-model.yaml` — normative requirements (VM-01 through
  VM-03)
- `vultron/wire/as2/vocab/base/registry.py` — implementation
- `vultron/wire/as2/vocab/base/base.py` — `as_Base` class
- `notes/activitystreams-semantics.md` — AS2 type model

## Registry Keys Are Disjoint: `VOCABULARY` vs. `WIRE_TYPE_MAP` (ARCH-23-002)

All classes in `vultron/wire/as2/vocab/objects/` use the `as_` prefix. The bare
name (`VulnerabilityCase`) always refers to the **core** domain model; the
prefixed name (`as_VulnerabilityCase`) is the wire type. See ARCH-14-001.

The two registries are keyed differently, and the distinction matters
(ARCH-23-002, issue #2941):

| Registry | Key | Example |
|---|---|---|
| `VOCABULARY` | full `as_*` class name | `"as_VulnerabilityCase"` |
| `WIRE_TYPE_MAP` | wire `type_` value | `"VulnerabilityCase"` |

The render adapter resolves a core class to its wire counterpart with
`WIRE_TYPE_MAP.get(type(obj).__name__)`. Never resolve a core type's wire
counterpart by name coincidence — use `WIRE_TYPE_MAP` (for `type_` values) or
`VOCABULARY` (for wire class-name lookups). The full pairing registry
(ARCH-23-001) is tracked by issue #2937.
