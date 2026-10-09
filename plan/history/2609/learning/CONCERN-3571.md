---
source: CONCERN-3571
timestamp: '2026-09-25T14:16:18.750293+00:00'
title: As2WireRenderAdapter resolves a core class name against the wire type-value
  index
type: learning
---

## Summary

`As2WireRenderAdapter.render()` resolves a core class to its wire counterpart with

```python
wire_cls = WIRE_TYPE_MAP.get(type(obj).__name__)
```

That is a **core class name** looked up in an index keyed by **wire `type` values**
(VM-01-007). It resolves only where the two strings happen to coincide, which is
the name-coincidence resolution ARCH-23-001 explicitly forbids:

> Resolving a counterpart by name coincidence between `VOCABULARY` and
> `CORE_VOCABULARY` is forbidden.

`notes/vocabulary-registry.md` documented this exact lookup as the sanctioned way
to resolve a counterpart, which is how it survived.

## Why it matters

For every core type whose name differs from its wire `type` value, the lookup
misses and `render()` raises `VultronValidationError("No wire counterpart for core
type 'X'.")` — a message that reads as "this type is not registered" when the real
cause is that the index cannot answer this question at all. The five core actor
types (`VultronPerson`, `VultronOrganization`, `VultronService`,
`VultronApplication`, `VultronGroup`) are in that position today.

Measured while fixing #2982: they raised *before* that fix too, because
`as_VultronPerson` is not an `as_VultronObject` and has no `from_core()`, so the
`issubclass` guard rejected it even when `WIRE_TYPE_MAP["VultronPerson"]` existed.
So removing the class-name keys changed nothing here — but it removed the last
thing that made the lookup look like it was working.

## Why it is not fixed in #3569

The correct fix is an explicit core↔wire pairing, and the mechanism ARCH-23-001
specified for that (the declarative pairing registry, ADR-0082 / #2937) is
**cancelled by ADR-0099**, which deletes the paired `as_*` domain classes instead.
Under one object model there is no counterpart to resolve and this lookup
disappears entirely.

So the real disposition question is whether ADR-0099 (currently *provisional*)
lands. If it does, this resolves itself. If it stalls, this lookup needs an
explicit index rather than a string coincidence, and ARCH-20-003's error message
should distinguish "no counterpart declared" from "cannot be resolved this way".

## Pointers

- `vultron/adapters/driven/wire_render/as2.py` (the lookup and its docstring)
- `specs/architecture.yaml` ARCH-23-001, ARCH-20-003
- `specs/vocabulary-model.yaml` VM-01-004, VM-01-007
- `notes/vocabulary-registry.md` § "Registry Keys Are Disjoint" (now records this
  honestly rather than presenting it as the sanctioned lookup)
- `docs/adr/0099-one-object-model-as2-is-a-serialization.md`

Surfaced by #2982 / #3569.

**Resolved**: 2026-09-25 — already fixed by #3490 (merged via #3676): `render()` is now the object's own `model_dump` (ARCH-20-002) and no class-name counterpart lookup remains. No implementation issue needed; the ARCH-23-001 rewrite is tracked by #3491. Stale text in `notes/vocabulary-registry.md` corrected.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3691>.
