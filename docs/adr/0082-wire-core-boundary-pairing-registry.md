---
status: accepted
date: 2026-08-31
deciders: Allen Householder
consulted: Claude Code (planning agent for G02 / CONCERN-2830)
informed: Vultron contributors
supersedes: 0062-normalise-wire-to-core-at-both-ingress-and-persistence.md
---

# Wire/Core Boundary: One Declarative Pairing Registry, One Translator, and Reject Unknown Keys

## Context and Problem Statement

Vultron carries two vocabularies for the same concepts. The wire branch (`as_*`
classes under `vultron/wire/as2/vocab/`) is the ActivityStreams 2.0 projection:
camelCase keys, AS2 `@context`, lenient field types. The core branch
(`CoreObject` subclasses under `vultron/core/models/`) is the domain model:
snake_case, narrowed types, and — since ADR-0036 — nested dimension objects
where the wire keeps flat fields. ADR-0017 established the two-branch hierarchy
and ADR-0062 established where wire→core normalisation happens.

The boundary between them exists in the type system but almost nothing enforces
it, and the knowledge needed to cross it is duplicated four ways.

**1. "Which fields are AS2 references" is known in three places.** The type
annotations (`as_ObjectRef`-typed fields) are the truth.
`_AS_OBJECT_REF_FIELDS` in `vultron/adapters/driven/db_record.py` is a
hand-maintained frozenset whose own comment describes it as "ActivityStreams
fields typed as `as_ObjectRef`" — a copy of the annotations that can drift. And
individual `to_core()` methods call `_scalar_ref_id_or_value(...)` on those
fields by hand, a third restatement.

**2. The core↔wire pairing is known in four places, none of them declarative.**
`As2WireRenderAdapter.render()` resolves a core class to its wire counterpart
with `VOCABULARY.get(type(obj).__name__)` — that is, it relies on the *bare-name
collision* between `VOCABULARY` and `CORE_VOCABULARY` as an implicit pairing
index. The collision is between *registry keys*, not class names: the wire class
is `as_CaseParticipant`, but it registers under the bare key `CaseParticipant`,
which is also the core class's `__name__`, so looking the core name up in
`VOCABULARY` happens to land on the wire counterpart.
`_WIRE_ACTOR_TO_CORE` in `vultron/wire/as2/vocab/objects/vultron_actor.py`
is a hand-rolled pairing table for actor types only, built because someone
needed exactly this mapping and no general one existed.
`_NORMALIZE_WIRE_TO_CORE` in `db_record.py` is a third hand-maintained list of
paired types. And three registries (`VOCABULARY`, `CORE_VOCABULARY`,
`CORE_TYPE_MAP`) are chained by `find_in_vocabulary()`.

This is why issue #2403 — "make the two `type_` namespaces disjoint" — has
looked risky rather than obvious: the collision it proposes to remove is
currently load-bearing. Fifteen wire registry keys shadow a core type's key, and
the render adapter depends on that shadowing to find its counterpart.

**3. Projection is declarative in one direction and hand-written in the other.**
`VultronAS2Object.from_core()` is generic: dump, apply the declarative
`_field_map` renames, validate. `to_core()` raises `NotImplementedError` at the
base and is overridden in twelve wire classes — 195 lines across the twelve
overrides plus the base raiser, against 152 lines of `from_core()`, so 354 lines
is the both-directions total. Six of those overrides are pure boilerplate around
one per-type fact:

```python
data = self._to_core_data()
data.pop("context_", None)                             # repeated 4x
data["attributed_to"] = _scalar_ref_id_or_value(...)   # repeated 3x
data["context"]       = _scalar_ref_id_or_value(...)   # repeated 3x
return CoreX.model_validate(data)                      # <- only per-type part
```

The single per-type element is *which core class to validate against* — the
pairing from (2). A generic `to_core()` mirroring the generic `from_core()` is
blocked only by the absence of a declarative pairing table.

**4. Boundary enforcement lives in three places.** ADR-0062 named this as its
own negative consequence: "the same projection is expressed in two places, and a
reader can reasonably wonder which one is authoritative." Since then a third
appeared — the per-class reject-guard in `CaseParticipant`.

Meanwhile the boundary is not actually closed. Pydantic v2 defaults to
`extra="ignore"`, so handing a wire-shaped payload to a core type silently
discards every key whose only spelling is snake_case. That is the #2232 defect:
`participantStatuses` dropped, the field left empty,
`_init_participant_status_if_empty` re-seeding one status at `RM.START`, and a
participant's RM ladder `['START','RECEIVED']` silently becoming `['START']`.
Issue #2232 fixed this for `CaseParticipant` alone; issue #2262 asks for the
general case. `CaseParticipant` is the only one of the eighteen
`CORE_VOCABULARY` entries carrying the guard, so the other seventeen registered
core types — and 29 of the 30 `CoreObject` subclasses overall — still drop
silently.

Separately, `test_wire_no_core_model_imports.py` carries an
`xfail(strict=True)` goal test asserting that `vultron/wire/` will eventually
have **zero** `vultron.core.models` imports. Issue #2670's acceptance criterion
is quoted as "all 29 entries removed"; that count is wrong at the source — the
issue's own enumeration lists 31 files, and `KNOWN_VIOLATIONS` in the ratchet
test holds 31 entries matching the 31 measured imports exactly. The target is
in any case unreachable while three MUST-level requirements stand: ARCH-12-001
mandates that `as_Base` inherit `VultronBase` (which lives in
`vultron/core/models/base.py`), ARCH-20-002 in its pre-ADR-0082 form mandates
that the rendering port's adapter locate the core object's wire counterpart and
invoke *that class's* `from_core()` projection —
so a wire class must keep a `from_core()` whose parameter is a core type — and
ARCH-12-010 mandates that `find_in_vocabulary()` consult the core
`CORE_TYPE_MAP`. An agent working #2670 would clear the easy files, reach the
base classes, and have to choose which MUST to violate. (ARCH-12-005 is easily
read as a fourth blocker and is not one: in its pre-ADR-0082 form it *permitted*
`to_core()`/`from_core()` on wire types and stated that they were not required
for structurally-compatible types.)

## Decision Drivers

- Silent data loss is the highest-severity item in scope. #2262 is a
  silent-drop default across the whole core vocabulary, and ARCH-15-001 /
  ARCH-15-002 already forbid exactly this failure mode.
- Serialized AS2 output must not change shape. Any namespace or registry change
  is internal.
- Piecemeal remediation of this area has a documented failure record:
  #1991 → #2232 → #2260 → #2268 → #2401/#2402, each fix creating the conditions
  for the next report. ADR-0063 made the same observation and chose to change
  all eight classes at once for that reason.
- Duplicated knowledge of the boundary is the mechanism behind that record. Each
  hand-maintained list (`_AS_OBJECT_REF_FIELDS`, `_WIRE_ACTOR_TO_CORE`,
  `_NORMALIZE_WIRE_TO_CORE`, `KNOWN_VIOLATIONS`) is a place where the true state
  and the recorded state can diverge silently.
- A goal test that asserts an unreachable state is worse than no goal test: it
  invites an implementer to violate a MUST in order to make it pass.
- ADR-0063 solved "core must not import wire" for *rendering* by introducing a
  driven port. The mirror-image rule, "wire must not import core" (ARCH-22), has
  never been addressed, and the *parsing* direction of ARCH-01-001 is still
  violated by core duck-typing a wire capability at three sites.

## Considered Options

- **Targeted camelCase reject-guard on `CoreObject`** — generalise the #2232
  `CaseParticipant` guard to the shared base.
- **`extra="forbid"` on `CoreObject`** — reject any unknown key, not just
  wire-spelled ones.
- **One declarative pairing registry plus one generic bidirectional translator,
  with `extra="forbid"` as the structural guarantee** — collapse all four
  duplications and delete the hand-maintained enforcement lists.
- **Keep the shared namespace and declare the collision intentional** — document
  the bare-name collision as the pairing index, amend VM-01-004 to match, and
  close #2403 as won't-do.

## Decision Outcome

Chosen option: **"One declarative pairing registry plus one generic
bidirectional translator, with `extra="forbid"` as the structural guarantee."**

The four duplications share one root cause: there is no single declarative
statement of what pairs with what. Every mechanism that needs the pairing
either re-derives it from a name collision or hand-maintains a private copy.
Introducing one authoritative pairing registry makes the other three
duplications collapse rather than requiring separate fixes, and it converts
issue #2403 from a risky rename into a consequence.

Concretely:

1. **A declarative pairing registry** becomes the single source of truth for
   core↔wire correspondence. It subsumes the bare-name collision that
   `As2WireRenderAdapter` relies on, `_WIRE_ACTOR_TO_CORE`, and
   `_NORMALIZE_WIRE_TO_CORE`. Once the pairing is explicit, `VOCABULARY` and
   `CORE_VOCABULARY` are free to use disjoint keys — which is what #2403 asked
   for, obtained as a by-product rather than as a rename with an unmeasured blast
   radius.

2. **AS2 ref-field sets are derived from the type annotations**, once.
   `_AS_OBJECT_REF_FIELDS` is deleted and the scattered
   `_scalar_ref_id_or_value(...)` calls in individual `to_core()` methods are
   replaced by the derived set. The annotations were always the truth; nothing
   else needs to restate them.

3. **A generic `to_core()` mirrors the generic `from_core()`**, driven by
   `_field_map`, the derived ref-field set, and the pairing registry. Six of the
   twelve hand-written overrides are deleted outright; `as_EmbargoEvent`'s
   reduces to a declarative drop-list. Only the genuinely structural
   projections — `as_VulnerabilityCase`, `as_CaseStatus`,
   `as_CaseParticipant`, which project nested children — keep bespoke code.

4. **Projection logic moves off the wire classes into translator modules on the
   adapter side.** This is what makes ARCH-22 achievable rather than
   redefined: wire classes become pure AS2 shape with no domain knowledge, and
   the translator modules — which are allowed to see both branches — own the
   pairing registry and the projection. ARCH-12-005 is amended accordingly.
   ADR-0063's *decision* stands; its *mechanism* is revised, because the render
   adapter no longer calls `wire_cls.from_core()` but delegates to the
   translator.

5. **A `WireParsePort` completes the ADR-0063 symmetry.** Core currently reaches
   for a wire capability by duck-typing — `getattr(obj, "to_core", None)` — at
   three sites, one of which is ADR-0062's primary ingress projection
   (`_project_to_core_participant` in
   `vultron/core/use_cases/received/case/_helpers.py`). These become port calls,
   which is the remedy ARCH-01-004 already prescribes and the one ADR-0063
   applied to the rendering direction.

6. **`extra="forbid"` on `CoreObject` is the boundary contract.** It is
   strictly stronger than a camelCase-specific guard: a typo, a renamed field,
   and a stale key are all caught, not only wire spellings. Two central
   cleanups are prerequisites, each defensible independently:

   - computed fields (`embargo_adherence`, a `@computed_field` per ADR-0056) must
     be stripped before re-validation, because they appear in `model_dump()`
     output but are not settable;
   - a `model_validator(mode="before")` must not inject an alias key beside a
     field-name key that the incoming payload already carries. `VultronBase`
     resolves `validate_by_name=True`, so both `id` and `id_` are sanctioned
     inputs — but only one of them may be present when validation proper begins,
     or the other is left over as `extra`. Each injecting validator must
     therefore normalise the payload to one spelling before writing its computed
     value.

   With `extra="forbid"` in place, `_NORMALIZE_WIRE_TO_CORE`, its grow-only
   ratchet test, and the per-class camelCase reject-guards are all dead code and
   are deleted. The invariant becomes a property of the type system rather than a
   list somebody must remember to update.

7. **ARCH-22-003 gains an explicit exemption clause.** Its "shrink toward empty"
   aspiration is retained, but the target becomes "empty except the declared
   structural exemptions", the exemption set is *enumerated* — one entry, the
   `find_in_core_type_map` import in `vultron/wire/as2/vocab/base/registry.py`,
   mandated by ARCH-12-010 — rather than stated as a count, and the
   `xfail(strict=True)` goal test is retargeted to equality with that
   enumeration. Everything else in the 31-entry ratchet set is a **relocation
   target, not an exemption**, and clears only when the relocation that owns it
   lands:

   - the shared-base and shared-primitive imports — the bulk of the set — clear
     when item 8 lands the branch-neutral module;
   - the projection imports in the `as_*` classes clear when item 4 moves
     `to_core()`/`from_core()` onto the adapter side;
   - `factories/actor.py` and `factories/case.py` clear only because AF-01-005 is
     amended here: in its pre-ADR-0082 form it *mandated* that the factory accept
     the core object and project internally, which pinned those two imports in
     place permanently. It is inverted to require a complete translator-produced
     wire object as the argument;
   - `vultron/wire/as2/enums.py` (`VultronActorType`) and the semantic extractor
     (`extractor/_instances.py`, `_builders.py`, `_pattern.py`, `_extract.py`,
     taking `VultronObjectType`, `MessageSemantics`, `VultronEvent`, `CoreActor`,
     `VultronCaseLedgerEntry` and the dimension types) are cross-cutting
     *vocabulary* rather than domain models, so the ADR-0031 neutral-layer
     treatment in item 8 is the likely answer — but each is its own relocation
     with its own task, and this ADR does not pre-judge them.

   Until all of those have landed, `KNOWN_VIOLATIONS` stays a superset of the
   exemption set and the two-sided ratchet (ARCH-22-002) stays in force. Stating
   the exemption set as an enumeration rather than a total is deliberate: a count
   in a requirement drifts the moment a relocation lands, and the residue is only
   reachable after all of them.

8. **The shared base moves to a neutral bottom layer.** `VultronBase` and
   `VultronObject` are shared by both branches, so hosting them in
   `vultron/core/models/base.py` makes every wire class a definitional ARCH-22
   violation. They move to a neutral layer, following the ADR-0031 precedent that
   introduced `vultron/enums/` for cross-cutting enumerations. The shared
   primitives (`NonEmptyString`, `UriString`, `VO_type`, `_now_utc`,
   `parse_duration`, `coerce_cvd_roles`, `coerce_em_consent_state`,
   `compute_genesis_hash`) move with them. ARCH-12-001 is amended to name the
   new home.

9. **`| CoreObject` is removed from `as_ObjectRef`.** The AS2-faithful part of
   that union — `as_Object | as_Link | str` — stays: the standard explicitly
   permits a property to hold an embedded object or an IRI reference, and
   `rehydrate()` (VM-06-001) resolves it at a defined point. The `| CoreObject`
   member is not AS2; it was added in PR #730 as a migration convenience and
   places a core type inside a wire annotation. Removing it is also what lets the
   boundary guard fail loudly: `VultronValidationError` is not a `ValueError`
   subclass, so a guard firing inside union resolution escapes the whole
   operation instead of being absorbed as a failed union branch.

### Measured evidence

The choice between options 1 and 2 was measured, not argued. A guard was
temporarily installed on `CoreObject` and the unit suite run:

| Configuration | Failing tests |
|---|---|
| Targeted camelCase reject-guard | 25 |
| `extra="forbid"`, no other change | 570 (plus 330 errors) |
| `extra="forbid"` + strip computed fields | 180 |
| `extra="forbid"` + strip computed + emit wire names in `_to_core_data` | 179 |

The initial 570 figure is misleading and was nearly decisive in the wrong
direction. **Not one** of those failures is a camelCase key. The rejected keys
are `embargo_adherence` (1096 occurrences) and `id_` (110) — our own code
failing to round-trip its own objects. Diagnosing that is what turned
`extra="forbid"` from "not viable" into "viable and stronger".

Two further findings came out of the same measurement:

- **The #2260 sequencing hazard does not exist.** Issue #2262 states that a
  `CoreObject` guard must be sequenced against #2260 because
  `ParticipantStatus` carries `alias_generator=to_camel` and legitimately
  accepts camelCase. Measured: any class carrying an alias generator yields an
  *empty* forbidden-key set. The guard is structurally inert on such classes and
  arms itself when #2288/#2289 remove the alias. No ordering constraint.
- **Persisted rows are keyed by Python field name, and one class cannot read its
  own back.** `Record.from_obj()` calls
  `obj.model_dump(mode="json", serialize_as_any=True)` with no `by_alias`, so
  rows are stored with `id_`/`type_` rather than `id`/`type`. That alone is
  harmless: `VultronBase` resolves `validate_by_name=True`, so `id_` is a
  sanctioned input and `Record.from_obj(p).to_obj().id_ == p.id_` round-trips.
  The 110 rejected `id_` keys are all one class. `CaseLedgerEntry`'s
  `_set_id_from_case` is a `model_validator(mode="before")` that writes
  `data["id"] = f"{case_id}/log/{log_index}"` into a payload that **already
  carries `id_`** from the dump; the alias satisfies the field, and the
  field-name key it was meant to replace survives as `extra`. Under
  `extra="ignore"` it is discarded silently; under `extra="forbid"` it raises.
  The same inject-an-alias-beside-the-field-name pattern occurs in
  `pending_case_inbox.py:73`, `pending_create_case_activity.py:97`,
  `case.py:130,166`, `case_participant.py:161,416,465`, `offer_record.py:82`,
  and — for `type` rather than `id` — `base.py:260`. The constraint that follows
  is not "emit wire-facing names everywhere"; it is "normalise to one spelling
  before injecting".

### Consequences

- Good, because the boundary invariant becomes a property of the type system.
  Four hand-maintained lists (`_AS_OBJECT_REF_FIELDS`, `_WIRE_ACTOR_TO_CORE`,
  `_NORMALIZE_WIRE_TO_CORE`, and the ratchet that guards it) are deleted rather
  than maintained.
- Good, because `extra="forbid"` catches failure modes a camelCase guard cannot:
  typos, renamed fields, and stale keys from an older schema.
- Good, because #2403 stops being a risky rename. Disjoint registry keys become
  safe once the pairing is explicit.
- Good, because ARCH-22's goal becomes reachable and honest. The ratchet's
  measured population is 31 files, not the 29 quoted in #2670, and the goal test
  targets an enumerated exemption set with a citation per entry: on the one
  exemption ARCH-12-010 mandates today that is 30 of 31 clearing, and any file
  that turns out not to clear is named and justified rather than pending.
- Good, because wire classes end up with no domain knowledge, which is what
  ADR-0017's "wire is a projection of core" asserted but never structurally
  enforced.
- Bad, because it is a wide change: 13 tasks touching the shared base, the
  vocabulary registries, the persistence round-trip, the render adapter, and the
  semantic extractor. It partially supersedes one ADR and revises the mechanism
  of another.
- Bad, because it revises ADR-0063, which was accepted 2026-08-13. The decision
  there was correct and stands; only the adapter's internal mechanism changes.
- Bad, because moving the shared base out of `vultron/core/models/` touches
  every core and wire model module's imports, even though the change is
  mechanical.
- Neutral, because serialized AS2 output does not change. The pairing registry
  and disjoint keys are internal; wire `"type"` values are unaffected.
- Neutral, because no data migration is implied. Existing rows keyed by `id_`
  still validate (`validate_by_name=True`), so re-keying rows to `id` is a
  consistency choice rather than a correctness requirement, and this code has no
  production deployment in any case.

## Validation

- `ParticipantStatus.model_validate({"rmState": "RECEIVED"})` and every other
  `CoreObject` subclass raise on an unknown key rather than silently dropping
  it, with a test per registered core type.
- An architecture test asserts every `CoreObject` subclass resolves
  `extra="forbid"` through its `model_config`, with no exemption list.
- `_NORMALIZE_WIRE_TO_CORE`, `test_normalize_wire_to_core_ratchet.py`,
  `_AS_OBJECT_REF_FIELDS`, and `_WIRE_ACTOR_TO_CORE` no longer exist; a grep
  test asserts their absence so they cannot be reintroduced.
- A round-trip test asserts that for every entry in the pairing registry,
  `to_core(from_core(core_obj))` equals `core_obj`, and that the wire
  serialization is byte-identical to the pre-change output — this is what
  guarantees "serialized AS2 output must not change shape".
- The pairing registry is asserted complete: every `CORE_VOCABULARY` entry with a
  wire counterpart appears in it, and every wire type claiming a core
  counterpart resolves.
- `test_wire_core_model_import_boundary_goal` XPASSes against the declared
  exemption set, and its `xfail` marker is deleted (#2673).
- No `vultron/core/` module contains `getattr(obj, "to_core", None)`; the three
  sites route through `WireParsePort`.

## Pros and Cons of the Options

### Targeted camelCase reject-guard on `CoreObject`

- Good, because the helper already exists and is generic per class
  (`reject_wire_spelled_keys` in `vultron/core/models/_wire_spelling.py`), so it
  is a wiring change rather than new machinery.
- Good, because it is the smallest change that stops the known bleeding —
  25 failing tests, roughly half of which are genuine silent-drop bugs on the
  Accept/Reject-Invite actor paths.
- Good, because its error message names the correct remedy ("convert at the
  wire→core boundary instead").
- Bad, because it catches only camelCase. A typo, a renamed field, or a stale key
  from an older schema still vanishes silently, so the defect class is narrowed
  rather than closed.
- Bad, because it leaves all four duplications in place, and therefore leaves the
  mechanism that produced #1991 → #2232 → #2260 → #2268 intact.

### `extra="forbid"` on `CoreObject` alone

- Good, because it closes the defect class rather than one spelling of it.
- Bad, because without the accompanying cleanups it fails 570 tests for reasons
  unrelated to the boundary — computed-field echoes and field-name round-trips —
  which would be read as evidence against the approach rather than as three
  bugs.
- Bad, because it does nothing about the pairing duplication, so #2403 and
  ARCH-22 remain as unresolved as before.

### One pairing registry plus one generic translator, with `extra="forbid"`

- Good, because one new declarative artifact causes three separate duplications
  to collapse, rather than three separate fixes.
- Good, because it resolves #2262, #2403, and the substance of #2670 under a
  single design, so the three cannot land inconsistently.
- Neutral, because the amount of *new* code is small — 354 lines of projection
  logic relocated and mostly deleted — while the amount of *touched* code is
  large.
- Bad, because it is the largest option and sequences 13 tasks, so the benefit
  arrives late.

### Keep the shared namespace; declare the collision intentional

- Good, because it is nearly free: amend VM-01-004 to describe what the code
  already does, and close #2403.
- Good, because the collision genuinely *is* semantically meaningful — the same
  concept in two representations arguably should share a name.
- Bad, because an implicit index is untestable. Nothing asserts that a core type
  and its wire counterpart agree on the name, so a rename silently breaks
  `As2WireRenderAdapter.render()` at runtime with "No wire counterpart".
- Bad, because it forgoes the collapse: the other three duplications still need
  three separate fixes, each with its own hand-maintained list.

## More Information

- Planning group **G02** (#2830), under the planning-group epic #2828.
- Members resolved by this decision: #2262 (silent drop across the core
  vocabulary), #2403 (disjoint `type_` namespaces).
- Members re-scoped rather than resolved: #1895 (ontology direction) and #891
  (JSON-LD library evaluation) are converted into dedicated Ideas under epic
  #890, carrying the evidence gathered here. This decision records **no**
  adopt-or-decline verdict on PyLD or `activitypubdantic`; that is deliberately
  deferred to those Ideas.
- **Partially supersedes ADR-0062** (`supersedes:` in this ADR's frontmatter,
  `partially_superseded_by:` in ADR-0062's; the project has no
  `partially_supersedes` field). ADR-0062 chose *two* enforcement points and
  only the second is replaced. **Survives:** normalise at ingress, so no core
  reader ever sees a wire shape — the placement stands, with its mechanism
  changed from a `to_core()` call to a `WireParsePort` call (item 5), exactly as
  ADR-0063's mechanism is revised below. Its "readers stay strict" consequence
  also stands. **Replaced:** the persistence-boundary backstop —
  `_NORMALIZE_WIRE_TO_CORE`, `_normalize_to_core()`, and the grow-only ratchet —
  which becomes unnecessary once `extra="forbid"` makes the invariant a property
  of the type system rather than a maintained list. ADR-0062 keeps
  `status: accepted` and remains authoritative for the current code until the
  task set lands.
- **Revises the mechanism of ADR-0063**, whose decision (render core objects
  through a driven port) stands unchanged.
- Related: ADR-0017 (two-branch hierarchy), ADR-0031 (neutral bottom layer
  precedent), ADR-0034 (`dl.read()` returns core objects), ADR-0036 (dimension
  objects), ADR-0056 (`embargo_adherence` as a computed field), ADR-0069
  (Vultron namespace URI).
- Related issues: #2232, #2260, #2268, #2288, #2289, #2401, #2402, #2416, #2670,
  #2673, #1991. Flag the conclusion to **G12** (#2596), which will need whatever
  contract this establishes.

Generated spec requirements: `architecture.yaml` ARCH-12-001, ARCH-12-003 and
ARCH-12-005 amended; ARCH-20-002, ARCH-20-008 and ARCH-20-009 re-pointed at the
adapter-side translator and `WireParsePort`; ARCH-22-001 and ARCH-22-003
amended; new group ARCH-23 (ARCH-23-001 through ARCH-23-006);
`activity-factories.yaml` AF-01-005 inverted to forbid in-factory projection;
`vocabulary-model.yaml` VM-01-004 amended.
