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
related_notes:
  - notes/activitystreams-semantics.md
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
VOCABULARY["Actor"] = as_Actor  # ← must stay

# vultron_actor.py — override specific concrete types only
VOCABULARY["Person"] = VultronPerson
VOCABULARY["Organization"] = VultronOrganization
```

**Why**: The registry-completeness test checks that every module under
`vocab/base/objects/` contributes at least one concrete registration.
A module with zero registrations indicates a structural gap (all
registrations were moved elsewhere) and causes the invariant check to fail.

## Related Files

- `specs/vocabulary-model.yaml` — normative requirements (VM-01 through
  VM-03)
- `vultron/wire/as2/vocab/base/registry.py` — implementation
- `vultron/wire/as2/vocab/base/base.py` — `as_Base` class
- `notes/activitystreams-semantics.md` — AS2 type model
