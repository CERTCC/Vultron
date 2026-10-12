---
title: "Vocabulary Registry — Design Rules"
status: active
kind: guidance
tags: [vocabulary, registry, wire, as2, deserialization]
description: >
  Design rules for the AS2 vocabulary registry: auto-registration via
  __init_subclass__, flat dict, VocabNamespace, the generated JSON-LD
  context, fail-fast lookup, CORE_TYPE_MAP, and disjoint registry keys.
  Operating rules live in vultron/wire/as2/vocab/AGENTS.md.
related_specs:
  - specs/vocabulary-model.yaml (VM-01 through VM-03, VM-06, VM-10)
  - specs/architecture.yaml (ARCH-12-001, ARCH-12-002, ARCH-12-003, ARCH-12-010,
    ARCH-14-001, ARCH-20-002, ARCH-23-002, ARCH-25-003)
  - specs/docs-build-workflow.yaml (DOCBW-03-005)
  - specs/message-validation.yaml (MV-04-003)
related_notes:
  - notes/activitystreams-semantics.md
  - notes/wire-core-boundary.md
  - notes/core-wire-rendering-port.md
  - notes/documentation-strategy.md
  - notes/datalayer-design.md
relevant_packages:
  - vultron/wire/as2/vocab
  - vultron/adapters/driven/wire_render
  - vultron/adapters/driven/trigger_activity_adapter
---

# Vocabulary Registry — Design Rules

Operating rules: `vultron/wire/as2/vocab/AGENTS.md`. Specs:
`specs/vocabulary-model.yaml`. Implementation:
`vultron/wire/as2/vocab/base/registry.py`.

## Registration

### 1. Auto-registration via `__init_subclass__`

`as_Base.__init_subclass__` registers every subclass that narrows `type_` to a
`Literal[...]`, at class-definition time; no decorator. Abstract bases
(`as_Object`, `as_Activity`, `as_Actor`, …) leave `type_` as `str | None` and are
skipped.

### 2. A concrete class MUST narrow `type_` to a `Literal`

`set_type_from_class_name` (VM-03-001) derives `type_` at construction for a
class with no annotation, but registration skips it, so the two mechanisms
disagree about which classes are concrete and registration is the silent one
(VM-03-002). `test_registry.py::TestWireTypeValues` walks the `as_Base`
subclasses and requires each class presenting its own type value to be what
`WIRE_TYPE_MAP` answers, with a per-class exemption set whose members each name
a reason.

### 3. Flat registry dict

The registry is one flat `dict[str, type[as_Base]]`; objects, activities and
links share one namespace with no collisions.

### 4. `VocabNamespace` is not a key, but it is load-bearing

Each `as_Base` subclass carries `_vocab_ns: ClassVar[VocabNamespace]`
(default `AS`; `as_VultronObject` sets `VULTRON`). The type name alone is the
key, because callers usually hold only the wire `type` string. But `_vocab_ns`
is the sole input to the generated JSON-LD `@context`, so a Vultron-specific type
left annotated `AS` ships without a `vultron:` term and receivers cannot resolve
it (VM-10-001, VM-10-002).

### 4a. `docs/ns/context.jsonld` is generated, never hand-edited

`uv run wire-context --write` (`vultron/metadata/wire_context/sync.py`)
generates it from every wire class whose `_vocab_ns` is `VULTRON`, keyed by the
emitted `type` value, so a class sharing another's `type` needs no term of its
own. When adding or renaming a wire type:

- Regenerate and commit the artifact. `uv run wire-context --check` (pre-commit)
  and `test_committed_context_is_not_stale` (CI) enforce it.
- Annotate a Vultron-specific type `VULTRON`.
  `test_non_as2_wire_types_are_annotated_vultron` checks against the AS2 term set
  from the *defining module*, never from `_vocab_ns` itself, which would blind
  the guard to the mistake it looks for.
- Keep the enumeration filter to classes defined under `vultron.wire.as2.vocab`:
  a class declared inside a test joins the subclass graph, and without the filter
  a test probe could inject a term into the normative document.

The document is normative but not reachable: `ns/` stays withheld from the
published site until #3653 moves it to the versioned URL ADR-0106 decided, and
`uv run docs-withheld` fails CI if a build publishes it (DOCBW-03-005).

### 5. Lookup fails fast on unknown types

`find_in_vocabulary()` raises `KeyError` for an unregistered name (VM-06-005):
a silent `None` lets corrupt deserialization proceed. A caller that should skip
unknown types catches `KeyError`.

### 6. Dynamic discovery is the startup guarantee

`vocab/objects/__init__.py` and `vocab/activities/__init__.py` import every
sibling module with `pkgutil.iter_modules`, because `__init_subclass__` fires
only for classes that are defined, and a never-imported module defines none.

## `CORE_TYPE_MAP` Is Core-Only

Core types never enter the wire `VOCABULARY` (ARCH-12-003). `CoreRecord` and
`CoreObject` subclasses auto-register in `CORE_TYPE_MAP`
(`vultron/core/models/registry.py`). The hook lives on `CoreRecord` because the
bookkeeping records extend it but not `CoreObject` (ARCH-12-010); ratchets
`test_core_record_types_in_core_type_map` and
`test_no_wire_types_in_core_type_map` hold both directions.

`find_in_vocabulary()` is wire-only unless the caller passes
`include_core=True` (VM-06-008). Only persistence read paths ask for the core
fallback. A wire-side caller must not (MV-04-003): a core class placed in a wire
tree is rejected by the parent's field type, so the fallback degrades the parent
instead of resolving the child. A hit there is a coincidence of naming, not a
wire counterpart. See [wire-core-boundary](wire-core-boundary.md).

A core collection model MUST NOT be reintroduced: `CoreActor.inbox` and
`.outbox` are URL strings (ARCH-12-006), and a core class declaring
`type_: Literal["OrderedCollection"]` squats the wire name in `CORE_TYPE_MAP`.

## Actor Overrides Keep `"Actor"`

A Vultron actor module overrides only the concrete actor keys it needs
(`Person`, `Organization`, `Service`, …); `"Actor"` stays mapped to `as_Actor`,
its only registration. The VM-01-007 ratchet refuses an `as_Actor` left
unreachable.

## Registry Keys Are Disjoint: `VOCABULARY` vs. `WIRE_TYPE_MAP`

Wire classes use the `as_` prefix (ARCH-14-001), but for a *domain* type the
prefixed name is an alias of the core class (ARCH-25-003) and holds no
`VOCABULARY` key. The prefix still marks a real wire class for unpaired AS2
vocabulary (`as_Link`, `as_Collection`, …).

| Registry | Key | Example | Spec |
|---|---|---|---|
| `VOCABULARY` | full `as_*` class name | `"as_Collection"` | VM-01-004 |
| `WIRE_TYPE_MAP` | emitted wire `type` value | `"Collection"` | VM-01-008 |

Both keys are derived by `as_Base.__init_subclass__`, `WIRE_TYPE_MAP` via
`wire_type_value()`. Two classes cannot own one `type` value, so a class that
shares another's declares `_wire_type_alias: ClassVar[bool] = True` and takes no
`WIRE_TYPE_MAP` key. The Vultron actor classes (`as_VultronPerson`, …) are
the only sanctioned unflagged sharers: they register after the base actors and
shadow them, so `{"type": "Person"}` gets the subclass carrying
`embargo_policy`. The ratchet fails on any other collision, which would silently
move the key to whichever class imports last
(`test/architecture/test_vocab_registry_keys.py`; disjointness from
`CORE_VOCABULARY` in `test/wire/as2/vocab/base/test_registry.py`). Do not
restate a key count in prose (MS-16-001).

**Never resolve a core type's wire counterpart by name.** Under ADR-0099 there
is none: `render()` is the object's own `model_dump` (ARCH-20-002), and the
declarative pairing registry (ARCH-23-001) was cancelled, not deferred; do not
revive #2937. `test_render_adapter_does_not_resolve_a_wire_counterpart` and
`test_package_does_not_resolve_a_wire_counterpart` refuse every name in
`REGISTRY_LOOKUP_NAMES` (`test/support/source_names.py`) in the render and
trigger adapters. They match direct name references only.
