# Vocabulary Registry — Design Rules

## Overview

The wire layer maintains a `VOCABULARY` registry mapping AS2 type names
to Python classes. This registry is the sole authoritative source for
dynamic deserialization: whenever an activity arrives over the wire or is
loaded from storage, the registry is consulted to find the correct
Pydantic class to instantiate.

Cross-references: `specs/vocabulary-model.yaml` VM-01;
`vultron/wire/as2/vocab/base/registry.py`

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

## Migration Path

1. **VOCAB-REG-1.1** (core mechanics): add `enums.py`, rewrite
   `registry.py`, add `__init_subclass__` to `as_Base`, override
   `_vocab_ns` on `VultronObject`, and add unit tests.
2. **VOCAB-REG-1.2** (migration): remove all `@activitystreams_*`
   decorators, add dynamic discovery to `__init__.py` files, update
   `find_in_vocabulary()` callers, and add a registration completeness
   test.

The refactor is backward-compatible for callers that use only
`find_in_vocabulary(name)`; the `item_type` parameter is removed because
no callers use it.

## Related Files

- `specs/vocabulary-model.yaml` — normative requirements (VM-01 through
  VM-03)
- `vultron/wire/as2/vocab/base/registry.py` — implementation
- `vultron/wire/as2/vocab/base/base.py` — `as_Base` class
- `notes/activitystreams-semantics.md` — AS2 type model
- `notes/spec-review-0327.md` — original registry fragility finding
  (VSR-06-001)
