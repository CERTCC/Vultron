---
title: "Wire/Core Boundary — Pairing Registry, Translator, and Unknown-Key Rejection"
status: active
tags: [wire, core, boundary, vocabulary, pairing, translation, pydantic]
description: >
  Design rationale for the wire/core boundary contract: one declarative pairing
  registry, one generic bidirectional translator on the adapter side, and
  extra="forbid" on the core branch as the structural guarantee. Records the
  four duplications this replaces and the measured evidence behind the choice.
related_specs:
  - specs/architecture.yaml
  - specs/vocabulary-model.yaml
related_notes:
  - notes/vocabulary-registry.md
  - notes/core-wire-rendering-port.md
  - notes/domain-model-separation.md
  - notes/datalayer-design.md
  - notes/activity-factories.md
  - notes/domain-validation.md
  - notes/status-dimension-objects.md
relevant_packages:
  - vultron/core/models
  - vultron/wire/as2/vocab
  - vultron/adapters/driven
---

# Wire/Core Boundary — Pairing Registry, Translator, and Unknown-Key Rejection

ADR: `docs/adr/0082-wire-core-boundary-pairing-registry.md`.
Specs: ARCH-12-001 through ARCH-12-005, ARCH-22, ARCH-23, VM-01-004.
Source: planning group G02 (#2830).

## The Two Rules Are Different, and Only One Was Solved

It is easy to conflate these, and doing so wastes a lot of time:

| Rule | Direction | Remedy |
|---|---|---|
| ARCH-01-001 | core MUST NOT import wire | `WireRenderPort` (ADR-0063) for rendering; `WireParsePort` (ADR-0082) for parsing |
| ARCH-22-001 | wire MUST NOT import core | move projection to the adapter side (ADR-0082) |

ADR-0063 solved the *rendering* half of the first rule. It did **not** touch the
second: its adapter is a thin dispatcher that still calls
`wire_cls.from_core(obj)`, so every wire class still imports its core
counterpart. Anyone reading ADR-0063 and concluding that wire→core imports were
addressed will misjudge the remaining work.

The *parsing* half of the first rule was also still open until ADR-0082: core
reached for a wire capability by duck-typing, `getattr(obj, "to_core", None)`, at
three sites — including ADR-0062's primary ingress projection in
`vultron/core/use_cases/received/case/_helpers.py`. Duck-typing does not satisfy
ARCH-01-001; it only hides the violation from the import-based ratchet.

## Why "Zero Wire→Core Imports" Was Unreachable

`#2670`'s acceptance criterion ("all 29 entries removed") and the
`xfail(strict=True)` goal test in
`test/architecture/test_wire_no_core_model_imports.py` both asserted that
`vultron/wire/` could reach zero `vultron.core.models` imports.

**The count is 31, not 29.** `len(KNOWN_VIOLATIONS) == len(_VIOLATIONS) == 31`
and their symmetric difference is empty, so the ratchet set is exactly the
measured set. The "29" in that acceptance criterion is #2670's own prose
miscount; do not propagate it. With the one declared exemption (ARCH-22-003), the
reachable target is **30 of 31 clear**.

Three MUST-level requirements made zero impossible:

- **ARCH-12-001** — `as_Base` MUST inherit `VultronBase`, which lived in
  `vultron/core/models/base.py`. A required inheritance is a permanent import.
- **ARCH-20-002** (as originally written) — the rendering adapter MUST locate the
  wire counterpart and invoke *that class's* `from_core()` projection, which
  constructs core objects at runtime. Cite **ARCH-20-002**, not ARCH-12-005, as
  the mandate here: pre-ADR-0082 ARCH-12-005 said the opposite — explicit
  `from_core()`/`to_core()` methods were "**not required** for
  structurally-compatible types". It is ARCH-20-002 that made the projection
  method load-bearing, and therefore the import permanent.
- **ARCH-12-010** — `find_in_vocabulary()` MUST consult the core
  `CORE_TYPE_MAP`.

An implementer working the easy files would reach the base classes and have to
choose which MUST to break. ADR-0082 removes the first two structural causes —
the shared base moves to a branch-neutral layer, and projection moves to the
adapter side — and retargets the goal test at a one-member exemption set.

**Lesson for future ratchets**: a goal test that asserts an unreachable state is
worse than no goal test — it invites an implementer to violate a MUST in order to
make it pass. Before adding one, check that the target does not contradict a MUST
elsewhere in the corpus. Then target the **declared exemption set, not empty**,
and enumerate each exemption together with the requirement that mandates it, so
the exemption is auditable rather than folklore (ARCH-22-003). The ARCH-22
exemption set currently has exactly one member: the `find_in_core_type_map`
import in `vultron/wire/as2/vocab/base/registry.py`, mandated by ARCH-12-010.

## The Four Duplications

The boundary needed one declarative statement and had none. Everything that
needed the pairing either re-derived it from a name collision or kept a private
copy.

**1. Which fields are AS2 references — three statements.** The `as_ObjectRef`
annotations are the truth. `_AS_OBJECT_REF_FIELDS` in `db_record.py` was a
hand-maintained frozenset whose own comment described it as "fields typed as
`as_ObjectRef`". Individual `to_core()` methods called
`_scalar_ref_id_or_value(...)` on those fields by hand.

**2. The core↔wire pairing — four statements, none declarative.**

- the bare-name collision between `VOCABULARY` and `CORE_VOCABULARY`, which
  `As2WireRenderAdapter.render()` used as its lookup:
  `VOCABULARY.get(type(obj).__name__)`
- `_WIRE_ACTOR_TO_CORE` in `vultron_actor.py` — a hand-rolled pairing table for
  actors only, built because the general one did not exist
- `_NORMALIZE_WIRE_TO_CORE` in `db_record.py` — a third list of paired types
- three registries chained by `find_in_vocabulary()`

This is why #2403 (disjoint `type_` namespaces) looked risky: **the collision was
load-bearing.** Removing it would have broken counterpart resolution. Make the
pairing explicit first and disjoint keys become safe — which is the order
ADR-0082 takes.

**3. Projection — declarative one way, hand-written the other.**
`from_core()` was generic, driven by the declarative `_field_map`. `to_core()`
raised `NotImplementedError` at the base and was overridden twelve times.
Measured over `vultron/wire/`: **`to_core()` is 195 lines across 13 defs,
`from_core()` 152 lines across 13** — so the 354-line figure quoted elsewhere is a
**both-directions** total, not `to_core()` alone. Six `to_core()` overrides were
boilerplate around one per-type fact:

```python
data = self._to_core_data()
data.pop("context_", None)                             # 4x
data["attributed_to"] = _scalar_ref_id_or_value(...)   # 3x
data["context"]       = _scalar_ref_id_or_value(...)   # 3x
return CoreX.model_validate(data)                      # <- the only variable
```

The variable part is the pairing from (2). That is the whole reason a generic
`to_core()` could not be written.

**4. Boundary enforcement — three places.** ADR-0062 listed this as its own
negative consequence ("the same projection is expressed in two places"). A third
appeared afterwards: the per-class reject-guard on `CaseParticipant`.

## Measured Evidence

Do not re-derive these; they were measured on the unit suite by temporarily
installing each guard on `CoreObject`.

| Configuration | Failing tests |
|---|---|
| Targeted camelCase reject-guard | 25 |
| `extra="forbid"`, nothing else | 570 (+330 errors) |
| `extra="forbid"` + strip computed fields | 180 |
| `extra="forbid"` + strip computed + wire-name keys in `_to_core_data` | 179 |

**The 570 figure is misleading and nearly decided this the wrong way.** Not one
of those failures involves a camelCase key. The rejected keys were
`embargo_adherence` (1096) and `id_` (110) — the project failing to re-read its
own serialized output. `embargo_adherence` is a `@computed_field` (ADR-0056): it
appears in `model_dump()` output but is not settable, so
`model_validate(model_dump(x))` fails under `extra="forbid"`. Diagnosing that is
what turned the approach from "not viable" into "viable and stronger". The `id_`
count has a different and narrower cause — see "The `id_` Failures Are an
Alias-Injection Bug" below, and do not scope work off the surface reading.

### Two by-products worth remembering

**The #2260 sequencing hazard does not exist.** #2262 asserted that a
`CoreObject`-level guard must be sequenced against #2260 because
`ParticipantStatus` carries `alias_generator=to_camel` and legitimately accepts
camelCase. Measured: a class carrying an alias generator yields an **empty**
forbidden-key set, because every field's camelCase form is a sanctioned
`validation_alias`. The guard is structurally inert on such classes and arms
itself when #2288/#2289 remove the alias. There is no ordering constraint.

**Persisted rows are keyed by Python field name.** `Record.from_obj()` calls
`obj.model_dump(mode="json", serialize_as_any=True)` with no `by_alias`, so rows
are stored with `id_`/`type_` rather than `id`/`type`. That is *not* a latent
read-back bug on its own — see the next section for why.

### The `id_` Failures Are an Alias-Injection Bug, Not a Field-Name Bug

Get this right before scoping #2933 or #2940: keying persistence on wire-facing
names would **not** fix the 110 `id_` failures, and would spend a migration on a
false premise.

**`id_` is a sanctioned input.** `VultronBase.model_config` resolves to
`validate_by_name=True` (alongside `populate_by_name=True` and
`validate_by_alias=True`), so a field declared `validation_alias="id"` accepts
**either** `id` or `id_`. Verified: `Record.from_obj(p).to_obj().id_ == p.id_`
round-trips, and a `ParticipantStatus` subclass with `extra="forbid"` validating
its own persisted row rejects only `embargo_adherence` — `id_` passes.

**The real mechanism.** All 110 `id_` failures are `CaseLedgerEntry`. Its
`mode="before"` validator `_set_id_from_case`
(`vultron/core/models/case_ledger_entry.py:154-159`) writes
`data["id"] = f"{case_id}/log/{log_index}"` into a payload that **already carries
`id_`**. Pydantic then consumes `id` via the alias and the field-name key `id_` is
left over as `extra`. Under `extra="forbid"` that is exactly one error,
`extra_forbidden` at `('id_',)`.

**Re-keying persistence would mask this, not fix it** — which is the worse
outcome. Verified: if the row is keyed `id`, the validator overwrites that key and
validation passes, *including* when the stored `id` disagrees with
`case_id`/`log_index` (a row carrying `id="urn:stale:different"` validates
silently to `urn:case:1/log/3`). Today the disagreement at least shows up as a
rejected key. So a persistence migration buys a silent overwrite, and it does
nothing for the `embargo_adherence` half of the blast radius, which is where the
1096 failures are.

**The constraint is therefore narrow**, and it is not "emit wire-facing names
everywhere":

> A `mode="before"` validator MUST NOT inject an alias key beside an
> already-present field-name key for the same field (or vice versa).

The same inject-alias-beside-field-name pattern appears at
`vultron/core/models/pending_case_inbox.py:73`,
`pending_create_case_activity.py:97`, `case.py:130,166`,
`case_participant.py:161,416,465`, `offer_record.py:82`, and
`base.py:260` (which writes `data["type"]`, the `type_` analogue). Each of those
is a site to fix, and the fix is to write the key the payload is already using —
not to re-key the database.

The round-trip cleanups (ARCH-23-005) are still prerequisites rather than
follow-ups, because the `@computed_field` half of the problem
(`embargo_adherence`, 1096 failures) is real and independent.

## `as_ObjectRef`: Which Part Is a Kludge

```python
as_ObjectRef = ActivityStreamRef[as_Object] | CoreObject | None
#   expands to:  as_Object | as_Link | str | None | CoreObject
```

**`as_Object | as_Link | str` is not a kludge.** AS2 explicitly permits a
property to hold either an embedded object or an IRI reference — that is how you
avoid shipping a whole case inside every message. `rehydrate()` (VM-06-001)
resolves it at a defined point.

**`| CoreObject` is the kludge.** Added in PR #730 as a migration convenience, it
places a core type inside a wire annotation — and therefore inside the `object_`
field of every transitive activity, `as_Collection.items`,
`as_Relationship.subject`/`.object`, and `as_Profile.describes`.

Beyond violating ARCH-22-001, it makes a core-side guard unsafe to enforce
loudly: **`VultronValidationError` is not a `ValueError` subclass**, so a guard
firing while Pydantic resolves that union escapes the entire operation rather
than being absorbed as a failed union branch. Any core-branch validator that
raises must either be removed from union exposure (the chosen path, ARCH-23-006)
or raise something Pydantic recognises as a validation failure.

## Related Files

- `docs/adr/0082-wire-core-boundary-pairing-registry.md` — the decision
- `docs/adr/0062-…` — superseded by 0081; still describes current code
- `docs/adr/0063-…` — decision stands, mechanism revised by 0081
- `vultron/core/models/_wire_spelling.py` — the camelCase guard, retired by
  ARCH-12-003's `extra="forbid"` clause
- `vultron/adapters/driven/wire_render/as2.py` — the render adapter whose
  name-collision lookup ARCH-23-001 replaces
- `test/architecture/test_wire_no_core_model_imports.py` — the ARCH-22 ratchet

## Deleting a Wire-Spelling Shim Without a Reject-Guard Is Silent Data Loss

Pydantic v2 defaults to `extra="ignore"`, so removing a validator that accepted a
legacy camelCase key makes that key *silently dropped* and the field default to
its start value — a lost RM ladder, not an error. Until `extra="forbid"` lands
everywhere, always pair the deletion with a `model_validator(mode="before")`
built on `reject_wire_spelled_keys` (`vultron/core/models/_wire_spelling.py`).
See SDO-03-005, ARCH-15-002.

**Superseded direction (ADR-0082)**: ARCH-12-003 now requires `extra="forbid"` on
all core-branch types, which subsumes this guard — it rejects any unknown key, not
only camelCase ones. Once that lands, `_wire_spelling.py` and the per-class guards
are deleted. Until then this pitfall still applies.
