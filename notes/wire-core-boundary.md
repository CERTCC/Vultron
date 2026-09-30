---
title: "Wire/Core Boundary — The Four Duplications and Why One Object Model Replaced the Pairing Registry"
status: active
tags: [wire, core, boundary, vocabulary, pairing, translation, pydantic]
description: >
  Diagnosis of the wire/core boundary problem: the four duplications, the measured
  evidence, and why "zero wire->core imports" was unreachable. The remedy it
  proposed (one declarative pairing registry, one adapter-side translator,
  extra="forbid" on the core branch) is superseded by ADR-0099, which removes the
  second hierarchy instead. Read it for the problem, not the mechanism. Also the
  home of the inbound unknown-key rule (MV-11): decided at the parse edge, not by
  class ancestry.
related_specs:
  - specs/architecture.yaml (ARCH-12-001, ARCH-12-002, ARCH-12-003, ARCH-20-008,
    ARCH-20-009, ARCH-21-002, ARCH-22-001, ARCH-23-005)
  - specs/code-style.yaml (CS-08-001, CS-08-002)
  - specs/error-handling.yaml (EH-07-001, EH-07-003)
  - specs/message-validation.yaml (MV-04-003, MV-11-001 through MV-11-005)
  - specs/status-dimension-objects.yaml (SDO-03-005)
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

> **Status: the diagnosis here stands; the remedy is superseded by
> [ADR-0099](../docs/adr/0099-one-object-model-as2-is-a-serialization.md).**
>
> Everything this note establishes about the *problem* is still accurate and
> still worth reading: the four duplications, the measured evidence, and the
> finding that "zero wire→core imports" was unreachable. Two things have since
> changed underneath it.
>
> The unreachability finding was correct but drew the wrong conclusion. Three
> MUSTs made zero impossible — so the rule was wrong, not the target. ARCH-22-001
> is repealed: it is not among ADR-0009's six Key Rules, it inverts the inward
> dependency direction hexagonal architecture prescribes, and it was itself the
> cause of the duplicate `as_*` classes it appeared to guard against.
>
> And the remedy — reconciling two hierarchies with a pairing registry and a
> generic translator — is replaced by removing the second hierarchy. Measured
> across the 27 paired classes, none of the 346 differing fields is a semantic
> disagreement. So the sections below that describe the ratchet, its
> `KNOWN_VIOLATIONS` inventory, the exemption set, and the pairing registry
> describe a plan that was cancelled. The migration is epic #2670.

ADR: `docs/adr/archived/0082-wire-core-boundary-pairing-registry.md`
(superseded by ADR-0099).
Specs: ARCH-12-001 through ARCH-12-005, ARCH-22, ARCH-23, VM-01-004.
Source: planning group G02 (#2830).

## The Two Rules Are Different, and Only One Was Solved

It is easy to conflate these, and doing so wastes a lot of time:

| Rule | Direction | Remedy |
|---|---|---|
| ARCH-01-001 | core MUST NOT import wire | `WireRenderPort` (ADR-0063) for rendering; for parsing, `rehydrate()` owns ID-to-object materialisation (VM-06-007) — the `WireParsePort` ADR-0082 proposed was rejected by ADR-0099 |
| ARCH-22-001 | ~~wire MUST NOT import core~~ — **repealed** (ADR-0099) | replaced by an allow-list: wire MAY import `core/models/` and `core/states/` only (#3483) |

ADR-0063 solved the *rendering* half of the first rule. It did **not** touch the
second: its adapter is a thin dispatcher that still calls
`wire_cls.from_core(obj)`, so every wire class still imports its core
counterpart. Anyone reading ADR-0063 and concluding that wire→core imports were
addressed will misjudge the remaining work.

The *parsing* half of the first rule was also still open when ADR-0082 was
written: core reached for a wire capability by duck-typing,
`getattr(obj, "to_core", None)`, at three sites — including ADR-0062's primary
ingress projection in `vultron/core/use_cases/received/case/_helpers.py`.
Duck-typing does not satisfy ARCH-01-001; it only hides the violation from the
import-based ratchet.

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

- **ARCH-12-001** (as originally written) — `as_Base` MUST inherit a shared
  root that lived in `vultron/core/models/base.py`. A required inheritance is a
  permanent import. ADR-0099 detail 4 has since deleted that root, and
  ARCH-12-001 now says the opposite: a wire class MUST NOT inherit a core
  class, and `as_Base` stands on `pydantic.BaseModel` directly.
- **ARCH-20-002** (as originally written) — the rendering adapter MUST locate the
  wire counterpart and invoke *that class's* `from_core()` projection, which
  constructs core objects at runtime. Cite **ARCH-20-002**, not ARCH-12-005, as
  the mandate here: pre-ADR-0082 ARCH-12-005 said the opposite — explicit
  `from_core()`/`to_core()` methods were "**not required** for
  structurally-compatible types". It is ARCH-20-002 that made the projection
  method load-bearing, and therefore the import permanent.
- **ARCH-12-010** — `find_in_vocabulary()` MUST be able to consult the core
  `CORE_TYPE_MAP`; since #3565 only when the caller passes `include_core=True`.

### ARCH-12-010 is a trap for wire-side callers

`find_in_vocabulary()` must be able to consult `CORE_TYPE_MAP`, and while that
fallback was the default, a **wire** caller that resolved an inline `type`
string through it got a core class placed inside a wire
tree, which the wire parent's field type then rejects. The measured case: an
inbound activity with an inline actor, whose `inbox` is typed `OrderedCollection`
— registered *only* in the core map — expanded to a core `CoreActorCollection`
that `as_VultronOrganization.inbox` refused, degrading **every inline actor** on
the inbound path to a bare `as_Link`. One instrumented suite run showed 52 hits,
all from this single cause, with no malformed input involved (ISSUE-3217).

The rule, now normative as **MV-04-003**: resolving an inline object's type
inside a wire tree MUST consider wire-branch classes only; an unresolved type is left for the parent field to
validate. "Wire-branch" means *held by the wire registry* — an `as_Base`
subclass or a class registered in `WIRE_TYPE_MAP` — not `as_Base` ancestry:
since ADR-0099 detail 3 the canonical `VulnerabilityCase` is a core class
registered as its own wire form, and an ancestry test would refuse it. A hit in
the core map is a **coincidence of naming**, not a wire
counterpart — the same disjointness ARCH-23-002 records for `VOCABULARY` and
`WIRE_TYPE_MAP`. Wire-branch field annotations MUST NOT name `CoreObject`
subclasses (ARCH-23-006; see § "`as_ObjectRef`: The Former Kludge" below for
the history). The *name lookup* path is the wrong way to place a core object
in a wire tree; the parent field annotation is the declared authority.

A filter inside one caller protected only that caller: the inbox adapter's
`_reparse_as_specific_type` had none and persisted a core class for an inbound
`{"type": "OrderedCollection"}`. The general rule is **VM-06-008**, which the
lookup itself has enforced since #3565: `find_in_vocabulary()` is wire-only by
default, and the core fallback is opt-in via `include_core=True`. Only the
persistence read paths opt in (`db_record.py`, `hydration.object_from_storage`),
each saying why at the call. ADR-0090. For `OrderedCollection` itself both causes are gone: the vestigial core class
`CoreActorCollection` was deleted (#3563) and the wire collection classes now
declare the `type_` they present, so the wire registry answers first (#3564).
Details are in
[vocabulary-registry](vocabulary-registry.md) § "Why `OrderedCollection` Collided
At All".

An implementer working the easy files would reach the base classes and have to
choose which MUST to break. ADR-0082 removed the first two structural causes —
the shared base was to move to a branch-neutral layer, and projection to the
adapter side — and retargeted the goal test at a one-member exemption set.
ADR-0099 superseded both moves: detail 4 deleted the shared base outright, and
the rendering adapter now dumps the core object itself (ARCH-20-002).

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

**Persisted rows now use wire-facing identity keys** (`id`/`type`/`@context`).
`Record.from_obj()` calls `_rekey_wire_identity()` after `_dehydrate_data()` to
rename the three identity keys before storage (#3546, ARCH-23-005).
Existing rows keyed `id_`/`type_` continue to round-trip correctly via
`populate_by_name=True`.
The alias-injection analysis in the next section remains accurate: `id_` is still
a sanctioned input on read-back, and re-keying did not mask the
`CaseLedgerEntry` bug because that bug is driven by the `_set_id_from_case`
validator injecting a duplicate key, not by key-name choice.

### The `id_` Failures Are an Alias-Injection Bug, Not a Field-Name Bug

Get this right before scoping #2933 or #2940: keying persistence on wire-facing
names would **not** fix the 110 `id_` failures, and would spend a migration on a
false premise.

**`id_` is a sanctioned input.** `CoreRecord.model_config` resolves to
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

All three halves of ARCH-23-005 are now met: translation (#2940),
persistence re-keying (#3546), and the refusal clause for a contradicted
`@computed_field` value (`embargo_adherence`, #3695) — see "`extra="forbid"` Is
the Boundary Contract" below for the refusal mechanism.

## `as_ObjectRef`: The Former Kludge, Re-Added On Purpose

**Removed in PR #3440** (ARCH-23-006), then **re-added deliberately in #3487**
once ADR-0099 made a core type in a wire slot the intended shape rather than a
migration convenience. Read this section for why it was a kludge the first time —
the reasoning is sound and the distinction between the two cases is the point.

The difference is the defect, not the union. `| CoreObject` was unsafe in PR #730
because a core-side guard firing inside that union escaped the whole operation:
`VultronValidationError` was not a `ValueError`, so Pydantic could not absorb it
as a failed branch. That is now fixed — the class inherits `ValueError`, and
`test_core_guard_inside_wire_union_fails_the_branch` holds the property — which is
exactly the precondition ARCH-23-006's note set before the rule could be inverted.
The fix was itself blocked until `VultronAlreadyExistsError` existed, because
`crud.create` signalled a duplicate row with a bare `ValueError` that ~60 call
sites swallow, so sharing the base made a projection failure indistinguishable
from "already stored".

For context on the original removal:

```python
# FORMER definition (PR #730 through PR #3440):
as_ObjectRef = ActivityStreamRef[as_Object] | CoreObject | None
#   expanded to:  as_Object | as_Link | str | None | CoreObject

# PR #3440 until #3487:
as_ObjectRef = ActivityStreamRef[as_Object] | None
#   expands to:  as_Object | as_Link | str | None

# CURRENT definition (#3487, ADR-0099):
as_ObjectRef = ActivityStreamRef[as_Object] | CoreObject | None
```

**`as_Object | as_Link | str` is not a kludge.** AS2 explicitly permits a
property to hold either an embedded object or an IRI reference — that is how you
avoid shipping a whole case inside every message. `rehydrate()` (VM-06-001)
resolves it at a defined point.

**The `str` branch is `NonEmptyString`** (#3876, CS-08-001). A blank IRI names
nothing, so `ActivityStreamRef`/`ActivityStreamRequiredRef` refuse it inbound
rather than carry it and let VM-07-001 drop it silently outbound. Inside a union
Pydantic keeps the `Annotated` wrapper, so code that classifies a branch with
`is str` or by set equality — `db_record._is_generic_object_ref`,
`rehydration._annotation_branches` — goes through `strip_annotated()`
(`vultron/core/models/_helpers.py`) first. Two ratchets derive the field set
from the annotations (ARCH-23-004) and assert the refusal:
`test/architecture/test_wire_reference_fields_reject_blank.py` and, for core
string fields with a pinned sentinel set,
`test_core_reference_fields_reject_blank.py`. The rule reaches only slots whose
annotation spells a string branch: the `Any | None` AS2 properties on
`as_Object` (`to`, `cc`, `bto`, `bcc`, `audience`, `attributedTo`, `inReplyTo`,
`context`, `url`, …) still admit a blank inbound, and neither ratchet can see a
string leaf in `Any`. Narrowing them is a design decision against ARCH-12-004's
declared leniency, tracked in #3894.

**`| CoreObject` was the kludge.** Added in PR #730 as a migration convenience, it
placed a core type inside a wire annotation — and therefore inside the `object_`
field of every transitive activity, `as_Collection.items`,
`as_Relationship.subject`/`.object`, and `as_Profile.describes`.

Beyond violating ARCH-22-001, it made a core-side guard unsafe to enforce
loudly: **`VultronValidationError` was not a `ValueError` subclass (until #3487)**, so a guard
firing while Pydantic resolved that union escaped the entire operation rather
than being absorbed as a failed union branch. Any core-branch validator that
raises must either be removed from union exposure (the chosen path, ARCH-23-006)
or raise something Pydantic recognises as a validation failure.

PR #3440 removed `| CoreObject` from both `as_ObjectRef` and
`as_ObjectRequiredRef`, and added the ARCH-23-006 architecture ratchet
(`test/architecture/test_wire_no_core_object_annotations.py`) to prevent
re-introduction. Factory functions that previously accepted `CoreActor` now
accept `as_Actor | str`; the adapter layer converts core objects to their wire
counterparts before passing them.

**Both halves of that were undone in #3487, and the ratchet was replaced rather
than widened.** The union is back on purpose; the adapter-side conversion has
nothing left to convert. The ratchet's replacement asserts the invariant detail 3
states — every promoted class is exactly AS2-representable — because the
alternative on offer was a 59-entry allowlist, which records violations without
checking anything.

One lesson worth keeping from the re-introduction: widening *some* of the slots is
worse than widening none. `as_Activity.actor` and `as_ObjectRef` were widened while
`target`/`origin`/`instrument` were not, so a promoted class in those three slots
escaped its declared union — malformed payloads outbound, refusals inbound, and
HTTP 422 on every `Create(VulnerabilityCase)`. The type errors that flagged it were
suppressed with `# type: ignore[assignment]`, so mypy and pyright stayed green
while the protocol did not work.

## Related Files

- `docs/adr/archived/0082-wire-core-boundary-pairing-registry.md` — the
  decision this note diagnoses for; superseded by ADR-0099 (#3492)
- `docs/adr/archived/0062-…` — superseded by 0082, which is itself superseded
- `docs/adr/0063-…` — decision stands; the 0082 mechanism revision never landed
- `docs/adr/0099-one-object-model-as2-is-a-serialization.md` — the decision
  that replaced the remedy
- `vultron/core/models/_wire_spelling.py` — the camelCase guard, retired by
  ARCH-12-003's `extra="forbid"` clause
- `vultron/adapters/driven/wire_render/as2.py` — the render adapter whose
  name-collision lookup ARCH-23-001 replaces
- `test/architecture/test_wire_core_import_allowlist.py` — the ARCH-22 allow-list, which replaced the ratchet (#3483). The ratchet file is deleted

## `extra="forbid"` Is the Boundary Contract (landed, #2940)

Pydantic v2 defaults to `extra="ignore"`, so historically removing a validator
that accepted a legacy camelCase key silently dropped that key and reset the
field to its start value — a lost RM ladder, not an error (the #2232 defect).

> **Under ADR-0099 the camelCase key is read, not refused.** #3487 put
> `alias_generator=to_camel` on `CoreObject` (detail 2), so `participantStatuses`
> is a declared alias of `participant_statuses` and lands in the right field. With
> `extra="forbid"` beside it, the only key still refused is one matching *no*
> field — a retired name or a typo — which is exactly the case that used to vanish.

`CoreObject` now sets `extra="forbid"` (ARCH-12-003): any **unknown** key on a
core type raises rather than being dropped. This **subsumed and retired** the
per-class camelCase reject-guards and `vultron/core/models/_wire_spelling.py`,
and the persistence-boundary normalisation gate (`_normalize_to_core`,
`_NORMALIZE_WIRE_TO_CORE`, `_project_shadowing_wire_obj`) — all deleted in #2940.
A wire-shaped row that is nonetheless persisted is projected to its core
counterpart on **read** (`hydration.project_wire_row_to_core`).

**Be precise about how much this rejects, because it is less than "a
wire-shaped payload fails loudly".** `forbid` rejects keys the model does not
know. Keys the model *does* know under a wire spelling are still accepted:

- `participantStatuses`, `caseRoles` and other camelCase spellings are
  **accepted** once #3487 lands: `CoreObject` derives them as aliases (ADR-0099
  detail 2), so they are read into their fields. Only a key matching no field
  raises.
- A flat `rm_state`/`rmState` on `ParticipantStatus`, or `em_state` on
  `CaseStatus`, is **accepted** — those spellings are declared `AliasChoices` on
  the dimension fields, so the value is *interpreted*, not dropped. That is not
  the #2232 defect (nothing is lost), but it does mean
  `CaseStatus.model_validate(as_CaseStatus(...).model_dump())` succeeds rather
  than failing, and so does the `CaseParticipant` equivalent. #2288/#2289, which
  would have made those spellings raise by removing the `alias_generator`, are
  closed as superseded by ADR-0099; #3578 owns reconciling ARCH-12-003.

Two invariants keep `extra="forbid"` self-consistent, both enforced by
validators on `CoreObject` (see `_check_computed_field_inputs` and
`_drop_alias_shadowed_field_names`):

- **Strip a matching computed field; refuse a contradicted one** (landed,
  #3695). A `@computed_field` (`embargo_adherence`, ADR-0056) appears in
  `model_dump()` output but is not settable, so a round-trip must drop it
  first. Dropping it *unconditionally* would silently erase a peer asserting
  adherence its own consent state denies, so ARCH-23-005 requires a supplied
  value that differs from the derived one to be refused instead (#3547).
  `_check_computed_field_inputs` is a `mode="wrap"` validator: it records every
  supplied spelling (field name, camelCase, declared alias), strips them, builds
  the object, then compares each supplied value against the derived one — a
  match against either the Python value or its `mode="json"` form is discarded,
  anything else raises `VultronProtocolViolationError` carrying one `Violation`
  per contradicted spelling (EH-07-003). Each spelling is checked on its own,
  so two disagreeing spellings cannot mask each other. Refusing was tried and
  reverted during #2940 triage because `as_ParticipantStatus` then had an
  independent settable `embargo_adherence`, so a wire row could legitimately
  disagree with core. That objection died with the second hierarchy: ADR-0099
  detail 3 aliases `as_ParticipantStatus` onto `ParticipantStatus`, and the
  `WireParsePort` the triage note waited on (#2938) is rejected, not pending.
  Measured on the unit suite, only two tests fed a self-contradictory row, and
  both fabricated it. A persisted row that contradicts itself now reads back as
  `None` from `dl.read()`, with a WARNING from `hydration.object_from_storage`
  naming the row and the cause — the row is not "not found", it is unreadable.
- **Never leave an alias key beside its field-name twin.** A `mode="before"`
  validator that derives a field and writes it under the alias (`id`) beside a
  dumped field-name key (`id_`) leaves an unconsumed twin that `extra="forbid"`
  rejects; the base de-dup validator drops the field-name twin (alias wins).

Ratchet: `test/architecture/test_core_extra_forbid.py` (every `CoreObject`
forbids extras with no exemption list; a dump round-trips exactly; the retired
mechanisms cannot be reintroduced). Deliberate wire→core snapshot
reconstruction in core nodes projects camelCase spellings via
`project_wire_snapshot_to_core`, which ARCH-20-008 names as the one seam core
has for a snapshot `dict`; the `WireParsePort` (#2938) that was to own it was
rejected by ADR-0099, so the helper is not interim.

## Inbound Unknown Keys Are Decided at the Parse Edge, Not by Class Ancestry (#3900)

`extra="forbid"` above answers one question: *did this process build or store
an object with a key it does not know?* That is always a bug. It was never a
decision about what a receiver does with a peer's property, but under one
object model it became one by accident. An inline domain object is a core
class, so an unknown key on it drew a 422; the envelope, a generic AS2 object,
a `Link` and an untyped inline dict are wire classes on `as_Base`, which keeps
Pydantic's default `extra="ignore"`, so the same key vanished with no log line.
Measured through `parse_activity` on 2026-09-30:

| Where the unknown key sat | Before MV-11 |
|---|---|
| envelope, `Note`, `Link`, untyped inline dict | dropped silently |
| envelope near miss (`Actor` beside `actor`) | dropped silently |
| envelope `attributed_to` (snake_case field name) | accepted — a declared spelling, both roots validate by name |
| inline `VulnerabilityCase`, inline `Organization` actor | refused, 422 |

The docs disagreed with each other about it too: ARCH-21-002 says inbound wire
data stays lenient, ARCH-12-003 forbids on every core object including inline
inbound ones, and the 2026-09-29 amendment of ADR-0099 detail 7 adopted
fail-loudly with an envelope carve-out that had no principle behind it beyond
"that is what the code does".

**The rule (MV-11, ADR-0099 details 7 and 8 as amended 2026-09-30).** The parser
is the inbound wire-to-core seam. It already walks every inline dict at every
depth, resolves each to its class, and knows the field path. So the disposition
is stated once there and holds everywhere:

1. Partition the arriving keys against the resolved class's declared spellings
   — field names, generated camelCase aliases, explicit validation aliases,
   `@context` (MV-11-001).
2. A **near miss** — the same string after lowercasing and removing
   non-alphanumerics, or a retired name — **refuses** the whole activity naming
   both spellings (MV-11-002). The sender meant a field we read; proceeding
   without it is the #2232 shape with a log line attached. Nothing fuzzier than
   that normalisation, ever: AS2 has too many short property names one
   character apart, and pinning down a richer "near" is not worth the time. A
   snake_case field name is **not** a near miss: both roots validate by name as
   well as by alias (CS-14-001, CS-14-002), so `attributed_to` is a declared
   spelling of `attributedTo`. The near misses are case and separator variants
   (`Actor`, `attributed-to`) and retired names.
3. Any **other** unknown key is **set aside and reported** at INFO with
   `activity_id`, the sender's `actor_id`, field path and key; the activity
   proceeds on its declared fields (MV-11-003). Never carry the key on the
   object — it would leak into the stored form, which `forbid` refuses
   (ISSUE-3489). The received evidence is the only copy.
4. **Core `forbid` is unchanged** (MV-11-004). The parse edge is the only door
   inbound data enters by, so a core class never sees an inbound unknown key.
   The retired-name list lives on the wire side and is consulted only at the
   parse edge; `ParticipantStatus._reject_retired_vfd_keys` is the one core
   guard SDO-03-005 already forbids, and it goes when the wire list arrives.
5. **Never re-validate from the raw body after parse** (MV-11-005, #3922).
   `inbox_storage._reparse_as_specific_type` re-parses an inline object from
   the raw request dict and falls back to a base class on failure with a DEBUG
   line. Once keys are set aside at parse, that path sees them again on a core
   class and silently stores the wrong type. Its purpose ended when the parser
   began resolving inline objects to their specific class (MV-04-003).

Ratchet: `test/wire/as2/test_unknown_key_disposition.py` — one matrix over
every position, `xfail(strict=True)` on the rows not yet built so the marks must
come off with the implementation (#3921).
