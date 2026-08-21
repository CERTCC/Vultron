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

## Related Files

- `vultron/wire/as2/vocab/base/registry.py` — implementation
- `vultron/wire/as2/vocab/base/base.py` — `as_Base.__init_subclass__`
- `notes/activitystreams-semantics.md` — AS2 type model
