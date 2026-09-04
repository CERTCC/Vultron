---
source: CONCERN-2830
timestamp: '2026-08-31T21:10:04.074351+00:00'
title: G02 wire/core boundary contract
type: learning
---

Planning group **G02** of 19 (#2830), under the planning-group epic #2828.
Members: #2262, #2403, #1895, #891. Domain epics: #2692, #890. Also rolled
in #2670 at maintainer request.

Docs PR: <https://github.com/CERTCC/Vultron/pull/2931>
ADR: `docs/adr/0081-wire-core-boundary-pairing-registry.md` (supersedes ADR-0062;
revises the mechanism of ADR-0063)
Notes: `notes/wire-core-boundary.md`
Specs: ARCH-12-001/002/003/005 and ARCH-22-003 amended; ARCH-23-001..006 added;
VM-01-004 amended.

## Decision

The four members were one problem stated four ways: the wire/core boundary's
knowledge is duplicated, and every mechanism needing the core↔wire pairing either
re-derives it from a bare-name collision or hand-maintains a private copy. The
decision is one declarative pairing registry plus one generic bidirectional
translator on the adapter side, with `extra="forbid"` on the core branch as the
structural guarantee.

## The four duplications

1. **Which fields are AS2 refs** — stated three times: the `as_ObjectRef`
   annotations (the truth), `_AS_OBJECT_REF_FIELDS` in `db_record.py` (a hand-copy
   whose own comment admits it restates the annotations), and hand-written
   `_scalar_ref_id_or_value(...)` calls in individual `to_core()` methods.
2. **The core↔wire pairing** — stated four times, declared nowhere: the bare-name
   collision `As2WireRenderAdapter.render()` relies on
   (`VOCABULARY.get(type(obj).__name__)`), `_WIRE_ACTOR_TO_CORE` (actors only),
   `_NORMALIZE_WIRE_TO_CORE`, and the three chained registries.
3. **Projection** — `from_core()` generic and declarative via `_field_map`;
   `to_core()` hand-written in twelve overrides (354 lines), six of them pure
   boilerplate whose only variable part is which core class to validate against.
4. **Boundary enforcement** in three places — ADR-0062 listed this as its own
   negative consequence, and a third (the `CaseParticipant` reject-guard) appeared
   afterwards.

## Measured evidence (spikes, reverted)

| Configuration | Failing tests |
|---|---|
| Targeted camelCase reject-guard on `CoreObject` | 25 |
| `extra="forbid"` alone | 570 (+330 errors) |
| `extra="forbid"` + strip computed fields | 180 |
| `extra="forbid"` + strip computed + wire-name keys | 179 |

**The 570 figure nearly decided this the wrong way.** Zero of those failures involve
a camelCase key. The rejected keys were `embargo_adherence` (1096) — a
`@computed_field` per ADR-0056 that appears in `model_dump()` output but is not
settable — and `id_` (110). Diagnosing that turned `extra="forbid"` from "not
viable" into "viable and strictly stronger than a camelCase guard".

Method note worth reusing: **read the failures before judging an approach by its
failure count.** A large count concentrated in two root causes is a different
situation from a large count spread across many.

## Three member premises were wrong

- **#2262's stated blocker does not exist.** It claimed sequencing against #2260
  because `ParticipantStatus` carries `alias_generator=to_camel`. Verified: any
  class with an alias generator yields an *empty* forbidden-key set, so the guard
  is inert there and arms itself when #2288/#2289 remove the alias.
- **#1895 is a paradigm mismatch, not a term gap.** The TTL models one class per
  semantic message (`RmCloseReport`, `EmProposeEmbargo`, `CsReadMsg`) — the retired
  shorthand paradigm — while the code models semantics as AS2 activity patterns
  (VAM) with no per-semantic type. It also declares
  `http://www.cert.org/ns/vultron_*#` while ADR-0069 adopted
  `https://certcc.github.io/Vultron/ns#`. And it treats the explicitly
  **non-normative** TTL as the contract while never mentioning the normative
  13-line `docs/ns/context.jsonld`.
- **#891's premise is wrong.** There is no JSON-LD processing at all — no
  expansion, compaction, or IRI resolution. `_expand_inline_value` in `parser.py`
  is Pydantic nested-dict hydration.

## ARCH-22-003's goal state was unreachable

The #2670 AC ("all 29 entries removed") and the `xfail(strict=True)` goal test
both asserted `vultron/wire/` could reach zero `vultron.core.models` imports. Three
MUST-level requirements each mandate one: ARCH-12-001 (shared-base inheritance),
ARCH-12-005 (projection methods, before ADR-0081), ARCH-12-010 (core type-map
fallback). An unreachable goal test invites an implementer to violate a MUST to
make it pass. Retargeted at an enumerated one-member exemption set.

Generalisable lesson, now an AGENTS.md pitfall: **check a ratchet's goal state
against the spec corpus before adding the xfail.**

## Other durable findings

- **ARCH-01-001 (core→wire) and ARCH-22-001 (wire→core) are different rules.**
  ADR-0063's `WireRenderPort` solved only the rendering half of the first; its
  adapter still calls `wire_cls.from_core()`, so it removed no wire→core imports.
  The parsing half was still served by core duck-typing
  `getattr(obj, "to_core", None)` at three sites — a violation the import-based
  ratchet cannot see.
- **A core-branch validator that raises must raise a `ValueError` subclass if its
  type is union-exposed.** `VultronValidationError` is not one, so a guard firing
  during Pydantic union resolution escapes the whole operation. `as_ObjectRef`
  carried `| CoreObject`, putting a core type in every transitive activity's
  `object_` field.
- **Persisted rows are keyed `id_`/`type_`**, not `id`/`type` —
  `Record.from_obj()` dumps without `by_alias`. Invisible only because unknown
  keys are ignored on read-back.
- **`by_alias=True` is the wrong fix** for the round-trip key problem: the wire
  class has `alias_generator=to_camel`, so it emits camelCase and makes things
  worse (verified). Rename only the trailing-underscore fields.
- ADR-0062's "covers 7 of the 15" consequence was stale — #2268/#2402 completed
  the set.

## Outcome

13 Tasks: #2932, #2933, #2934, #2935, #2936, #2937, #2938, #2939, #2940, #2941,
plus #2942, #2943 and #2944 (7 under #2670, 6 under #2692). 28 of 29 ARCH-22 violations
clear; the remainder is the `find_in_core_type_map` import ARCH-12-010 mandates.

3 Ideas under #890: #2945 (ontology direction, supersedes #1895), #2946
(PyLD), #2947 (`activitypubdantic`).

Closed: #2830, #2262, #2403, #1895, #891. **AC-3 knowingly unmet** — the
PyLD/`activitypubdantic` adopt-or-decline verdict was deferred to #2946/#2947 per
maintainer direction. #2670 kept its body intact and was decomposed instead.
