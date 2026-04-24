---
title: Vocabulary Registry Design
status: active
description: >
  Design notes for the Vultron wire vocabulary registry: AS2 type-to-class
  mapping and dynamic deserialization.
related_specs:
  - specs/vocabulary-model.md
related_notes:
  - notes/activitystreams-semantics.md
---

# Vocabulary Registry Design

## Overview

The Vultron wire layer maintains a `VOCABULARY` registry mapping AS2 type
names to Python classes. This registry is the sole authoritative source for
dynamic deserialization: whenever an activity arrives over the wire or is
loaded from storage, the registry is consulted to find the correct Pydantic
class to instantiate.

This note captures the design decisions made for the VOCAB-REG-1 refactor.

**Cross-references**: `specs/vocabulary-model.md` VM-01,
`vultron/wire/as2/vocab/base/registry.py`

---

## Problem Statement

The original registry populated itself as a side-effect of class decorator
application:

```python
@activitystreams_object  # writes to VOCABULARY.objects at import time
class VulnerabilityCase(VultronObject): ...
```

This created two fragility points:

1. **Population fragility** — if a vocab module is never imported by any
   application code path, its classes never appear in the registry.
   Deserialization silently fails.
2. **Developer overhead** — every new vocabulary class requires the developer
   to: (a) add the decorator, and (b) add an import to `__init__.py`.

The `spec-review-0327.md` review identified this as a cross-cutting risk
(item VSR-06-001).

---

## Design Decisions

### 1. Auto-registration via `__init_subclass__`

**Decision**: Move registration into `as_Base.__init_subclass__`. Every new
subclass of `as_Base` that narrows `type_` to a `Literal[...]` annotation is
automatically registered at class-definition time — no decorator needed.

**Rationale**: `__init_subclass__` is explicit in the class hierarchy (visible
at the base class definition), deterministic (fires exactly once per subclass
definition), and zero-overhead for new classes (no decorator to remember).

**Alternative rejected**: Dynamic-discovery-only (auto-import all sibling
modules from `__init__.py`). This approach was considered and rejected as the
primary mechanism because import side-effects are non-obvious to developers.
Dynamic discovery is retained as a **startup guarantee** (see below).

### 2. Concrete vs. abstract class detection

**Decision**: Use the `type_` field annotation as the heuristic. A class is
treated as concrete (and registered) if its `type_` annotation is
`Literal[...]`. Abstract/intermediate bases (e.g., `as_Object`, `as_Activity`,
`VultronObject`, `as_Actor`) leave `type_` typed as `str | None` and are
therefore skipped.

**Rationale**: No boilerplate needed on abstract classes; the pattern is
already established in the codebase (concrete classes narrow `type_` to a
Literal as part of VM-03-002).

### 3. Flat registry dict

**Decision**: Replace the three-sub-dict `Vocabulary(BaseModel)` with a single
flat `dict[str, type[as_Base]]` module-level singleton.

**Rationale**: No name collisions exist across objects/activities/links in the
current vocabulary. The `item_type` filter in `find_in_vocabulary()` is
vestigial; all callers use the plain `find_in_vocabulary(name)` form. A flat
dict is simpler to reason about and query.

### 4. `VocabNamespace` as metadata, not key discriminator

**Decision**: Introduce a `VocabNamespace` enum (`AS`, `VULTRON`) in
`vultron/wire/as2/vocab/base/enums.py`. Each `as_Base` subclass carries a
`_vocab_ns: ClassVar[VocabNamespace]` attribute (default: `VocabNamespace.AS`).
`VultronObject` overrides it to `VocabNamespace.VULTRON`.

Namespace is **not** part of the dict key — the type name alone is the key.
Namespace is introspectable on the class for debugging and potential future
filtering.

**Rationale**: Most callers of `find_in_vocabulary()` have only a type name
string (from the wire `"type"` field). Including namespace in the key would
require callers to know it, forcing a scan of all namespaces anyway.

Vultron activities (e.g., `RmCreateReportActivity`) directly subclass AS2 base
activity types with no `VultronActivity` intermediate class. Without such a
class, a namespace-as-key approach would require a separate per-class annotation
on every Vultron activity class — exactly the manual overhead the refactor is
trying to eliminate.

### 5. Fail-fast on unknown types

**Decision**: `find_in_vocabulary()` MUST raise `KeyError` when the requested
type name is not in the registry.

**Rationale**: A missing type indicates a registration gap that must be fixed
before deployment (VM-06-005). Silent `None` returns allow corrupt deserialization
to proceed undetected. All five current callers already manually raise
`KeyError` / `ValueError` / `HTTPException` after checking for `None`; making
the function itself raise is DRY and consistent.

**Migration note**: The `datalayer_tinydb.py` caller uses `if vocab_cls is not
None` to silently skip unknown types during list/read. This behavior must be
preserved by wrapping the call in a `try/except KeyError` rather than a `None`
check.

### 6. Dynamic discovery as startup guarantee

**Decision**: `vocab/objects/__init__.py` and `vocab/activities/__init__.py`
each use `pkgutil.iter_modules` + `importlib.import_module` to import all
sibling modules at package import time.

**Rationale**: `__init_subclass__` only fires at class-definition time. If
a vocab module is never imported by application code, its classes are never
defined and never registered. Dynamic discovery in `__init__.py` provides a
single startup guarantee that all vocab modules are loaded — without requiring
each application code path to explicitly import them.

---

## Migration Path

1. **VOCAB-REG-1.1** (core mechanics): Add `enums.py`, rewrite `registry.py`,
   add `__init_subclass__` to `as_Base`, override `_vocab_ns` on
   `VultronObject`. Add unit tests.
2. **VOCAB-REG-1.2** (migration): Remove all `@activitystreams_*` decorators,
   add dynamic discovery to `__init__.py` files, update `find_in_vocabulary()`
   callers, add registration completeness test.

The refactor is backward-compatible for callers that use only `find_in_vocabulary(name)`;
the `item_type` parameter is removed (no callers use it).

---

## Related

- `specs/vocabulary-model.md` — normative requirements (VM-01 through VM-03)
- `vultron/wire/as2/vocab/base/registry.py` — implementation
- `vultron/wire/as2/vocab/base/base.py` — `as_Base` class
- `notes/activitystreams-semantics.md` — AS2 type model
- `notes/spec-review-0327.md` — original registry fragility finding (VSR-06-001)
