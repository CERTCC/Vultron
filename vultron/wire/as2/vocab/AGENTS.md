# Vocabulary Registry — Design Rules

> Full design rationale, migration path, and registry mechanics:
> [`notes/vocabulary-registry.md`](../../../../notes/vocabulary-registry.md)
>
> Spec: `specs/vocabulary-model.yaml` (VM-01 through VM-03)

## Core Rules (MUST)

1. New vocabulary classes MUST NOT use `@activitystreams_object` or
   `@activitystreams_activity` decorators. Registration is automatic via
   `as_Base.__init_subclass__` when a class sets `type_` to `Literal[...]`.

2. `find_in_vocabulary()` checks `WIRE_TYPE_MAP`, then `VOCABULARY`, then falls
   back to `CORE_TYPE_MAP` (core domain types that MUST NOT appear in the wire
   `VOCABULARY` per ARCH-12-003). It MUST raise `KeyError` for names not
   found in any registry — never return `None`. Callers that previously
   checked `if vocab_cls is not None` must use `try/except KeyError` instead.
   Do NOT add core-layer types to `VOCABULARY` as a workaround for a
   missing lookup — fix the registration in `CORE_TYPE_MAP` instead.

3. The two registries carry **different key forms and you MUST NOT mix them**:
   `VOCABULARY` is keyed by wire class name (`as_VultronPerson`, VM-01-004),
   `WIRE_TYPE_MAP` by the emitted wire `type` value (`Person`, VM-01-008). Both
   are filled by `as_Base.__init_subclass__` — `VOCABULARY` from `cls.__name__`,
   `WIRE_TYPE_MAP` from `wire_type_value()` — so do not hand-assign a
   `WIRE_TYPE_MAP` key. The sole exception is `as_Actor`, which declares no
   `type_` of its own (so auto-registration skips it) yet is stored concretely
   as `type_="Actor"`. If a new class shares an existing class's `type` value,
   declare `_wire_type_alias: ClassVar[bool] = True` on it rather than letting
   import order decide who owns the key; it stays reachable through
   `VOCABULARY`. The only unflagged sharers are the five `as_Vultron*` actor
   shadows, enumerated in the ratchet `test/architecture/test_vocab_registry_keys.py`,
   which fails on any other collision.

## The Wire Branch Inherits Nothing From Core

`as_Base` in `vultron/wire/as2/vocab/base/base.py` stands on
`pydantic.BaseModel` directly (ARCH-12-001), and `as_Object.model_config` is
just `ConfigDict(frozen=True)`. The old `validate_assignment=False` override on
`as_Object` and the `_is_core_branch` sentinel are gone: they existed only to
cancel what the wire branch inherited from the shared core root, which
ADR-0099 detail 4 deleted. `validate_assignment` now lives on the core
`CoreRecord` root, which no wire class inherits, so the wire branch stays
lenient for inbound AS2 data without an override (ARCH-21-002).

Do not make a wire class subclass `CoreRecord` or `CoreObject` to reuse a
field or hook. Ratchet: `test_wire_vocabulary_inherits_nothing_from_core` in
`test/architecture/test_hierarchy_invariants.py`. Rationale:
`notes/core-wire-rendering-port.md` § "The `as_Object.model_config` override is
gone, and why".
*Source: ISSUE-2294, ADR-0099*

## Related Files

- `vultron/wire/as2/vocab/base/registry.py` — implementation
- `vultron/wire/as2/vocab/base/base.py` — `as_Base.__init_subclass__`
- `notes/activitystreams-semantics.md` — AS2 type model
