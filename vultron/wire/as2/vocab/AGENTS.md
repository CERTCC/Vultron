# Vocabulary Registry — Design Rules

> Full design rationale, migration path, and registry mechanics:
> [`notes/vocabulary-registry.md`](../../../../notes/vocabulary-registry.md)
>
> Spec: `specs/vocabulary-model.yaml` (VM-01 through VM-03)

## Core Rules (MUST)

1. New vocabulary classes MUST NOT use `@activitystreams_object` or
   `@activitystreams_activity` decorators. Registration is automatic via
   `as_Base.__init_subclass__` when a class sets `type_` to `Literal[...]`.

2. `find_in_vocabulary()` checks `VOCABULARY` first, then falls back to
   `CORE_TYPE_MAP` (core domain types that MUST NOT appear in the wire
   `VOCABULARY` per ARCH-12-003). It MUST raise `KeyError` for names not
   found in either registry — never return `None`. Callers that previously
   checked `if vocab_cls is not None` must use `try/except KeyError` instead.
   Do NOT add core-layer types to `VOCABULARY` as a workaround for a
   missing lookup — fix the registration in `CORE_TYPE_MAP` instead.

## `as_Object.model_config` Is Load-Bearing — Do Not Remove It

`as_Object` in `vultron/wire/as2/vocab/base/objects/base.py` carries
`model_config = ConfigDict(validate_assignment=False)`. This blocks cross-branch
MRO inheritance of `validate_assignment=True` (set by `ValidatedAssignmentMixin`
on `VultronObject`) from propagating to all 65 wire vocabulary classes (ARCH-12-002
requires the wire branch to stay lenient for inbound AS2 data).

Any change to `VultronObject.model_config` MUST also update `as_Object.model_config`
if the change should not propagate to wire subclasses. See
`notes/core-wire-rendering-port.md` § "`as_Object.model_config` Override Is Load-Bearing
Infrastructure" for the full rationale.
*Source: ISSUE-2294*

## Related Files

- `vultron/wire/as2/vocab/base/registry.py` — implementation
- `vultron/wire/as2/vocab/base/base.py` — `as_Base.__init_subclass__`
- `notes/activitystreams-semantics.md` — AS2 type model
