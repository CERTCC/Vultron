---
status: accepted-provisional
date: 2026-09-21
deciders: Allen D. Householder
consulted: notes/wire-core-boundary.md, notes/domain-model-separation.md
stakeholder_type: [project-contributor]
---

# One Object Model: AS2 Is a Serialization of the Core Model, Not a Parallel Hierarchy

> **Implementation status as of 2026-09-22: decided, partially built.**
> The decision details below are in the present tense because they state the
> decision, not the state of the code — that is the MADR convention. Four pieces
> have landed, each with a test that holds it:
>
> | detail | what landed | issue |
> |---|---|---|
> | 2 | AS2 spellings are out of core logic; the spelling is derived from the field alias | #3485 |
> | 5 | dimension objects serialize to a bare state value — validated by the spike under [Validation](#validation) | — |
> | 6 | ARCH-22-001 replaced by the wire→core allow-list | #3483 |
> | 9 | `rehydrate()` named and implemented as the owner of ID-to-object materialisation (VM-06-007) | #3486 |
> | 3 | all 27 paired `as_*` domain classes deleted; message slots name the core class | #3487, #3488 |
>
> The four misnamed wire classes were also renamed to `as_*` (#3484).
>
> **Details 1, 4, 7, 8 and 10 are not built.** Detail 9's other half — the object
> slots themselves holding whole objects — was unblocked by detail 3 and now
> materialises promoted core classes. Item-by-item
> status is in [Migration](#migration), which is transitional and should be
> deleted once the work lands.

## Context and Problem Statement

The project has carried three successive positions on the relationship between
the domain model and the ActivityStreams 2.0 (AS2) wire format:

1. **Everything is an AS2 object.** The domain types lived under
   `vultron/wire/as2/vocab/objects/` and inherited the AS2 class hierarchy.
2. **Core is different.** ADR-0017 (as first written, Option B) introduced a
   parallel, independent `CoreObject` hierarchy under `vultron/core/models/`.
3. **Core and wire share a lenient root.** ADR-0017 was amended two days later
   to Option D, connecting both hierarchies at a shared `VultronBase` /
   `VultronObject` root, because fully independent hierarchies blocked the
   `from_core()` / `to_core()` translation protocol.

Position 3 is neither one model nor two. It has produced a recurring stream of
structural repairs rather than converging: `_NORMALIZE_WIRE_TO_CORE`
(ADR-0062), the `_is_core_branch` sentinel (#2416), the `| CoreObject` union in
`as_ObjectRef` and its removal (#2935, ARCH-23-006), the wire-spelling
reject-guards (ARCH-15-002), the `ValidatedAssignmentMixin` threading dance
(ADR-0064, ARCH-21-002), the pairing registry (ADR-0082, ARCH-23-001), and the
branch-neutral-layer relocation chain (#2932, #2933).

Two further facts made the position unstable rather than merely costly:

- **ADR-0082 removed position 3's own justification.** Amended ARCH-12-005 now
  *forbids* `from_core()` / `to_core()` on wire vocabulary classes and moves
  translation to adapter-side translators. The per-class translation protocol
  was the sole reason ADR-0017 abandoned independent hierarchies. Nobody
  re-derived whether the shared root was still needed once that protocol was
  removed.
- **ARCH-22-001 ("wire MUST NOT import core") is not derived from ADR-0009.**
  The hexagonal-architecture ADR lists six Key Rules; none of them is a
  wire→core prohibition. Its rule 6 is *"the `wire/` layer is replaceable as a
  unit without touching `core/`"* — a constraint that wire→core imports
  satisfy. ARCH-22-001 cites ADR-0017, 0032, 0063 and 0082, never ADR-0009. It
  reads as a symmetric mirror of ARCH-01-001, but hexagonal dependency rules
  are asymmetric by design: outer layers depend inward.

This ADR settles the question at the level the previous three positions did
not: what the object hierarchy is *for*.

## Decision Drivers

- Stop the recurring structural repairs. Each individual fix has been
  defensible; the sequence is the defect.
- Preserve the ability to replace AS2 with a different wire representation
  later. This is the stated reason the layers were kept separate, and it is as
  yet unrealised and unplanned.
- Do not force core to adopt a wire representation that is wrong for internal
  use. AS2's *semantics* — activities as verbs, objects as nouns, "who does
  what to which object in what context" — match what core needs to express.
  AS2's *serialization choices* — camelCase, `@context`, inline-or-IRI
  polymorphism, optional-everything — do not.
- Keep Python naming idiomatic: snake_case field names in core.
- Keep the two kinds of object distinguishable. Conflating a wire object with a
  core object was the original defect that motivated the split (#2232, #2264).
- Fail loudly. Silent field loss (#2262) is the failure mode to eliminate.

## Considered Options

1. **One object model; AS2 is a serialization of it.** Core classes are the
   model. AS2 field names are aliases on those classes. The wire layer holds
   the AS2 envelope and message shapes, whose slots are typed with core
   classes.
2. **Relocate the shared root to a branch-neutral layer** (#2933, the status
   quo plan). Keeps both hierarchies and the machinery that reconciles them.
3. **Two fully independent hierarchies plus a translator.** Delete the shared
   root but keep both class families, bridged only by an explicit translator.
4. **Adopt a third-party AS2 hierarchy** (`activitypubdantic`, #2947) as the
   wire half.

## Decision Outcome

Chosen option: **Option 1 — one object model; AS2 is a serialization of it.**

The measured evidence (see *More Information*) shows the two "hierarchies" are
not two models. Across the 27 class pairs that have both a core and a wire
form, 346 fields differ, and not one of those differences is a semantic
disagreement. 71% are one side declining to state a type the other side already
states. 14.5% are `Any` on the core side specifically because ARCH-01-001
forbids core from naming a wire type. The remainder is AS2's inline-or-IRI
reference form plus `type_` expressed as an enum on one side and a `Literal` on
the other. Exactly two of the 27 pairs differ by field *name* rather than by
spelling, and both are the status classes covered by ADR-0036.

### Decision details

1. **One set of classes, serialized two different ways at two different
   boundaries.** The classes under `vultron/core/models/` are the object model.
   There is no second set of classes. Those same classes are written out
   differently depending on where they are going:

   | boundary | call | spelling |
   |---|---|---|
   | inter-actor delivery over HTTP | `model_dump_json(by_alias=True)` | AS2 — camelCase plus `@context` |
   | persistence to the data layer | `model_dump(mode="json")`, no `by_alias` | Python field names (`id_`, `type_`) |

   **AS2 is the HTTP transmission format only.** Stored rows are not AS2-spelled
   today and this decision does not change that. A received activity is
   additionally kept verbatim as an unparsed `dict[str, Any]` in the ledger
   payload snapshot (CLP-07-001); that copy is neither serialization above — it
   is the bytes as they arrived.
2. **Core field names follow Python convention; the AS2 spelling lives in a
   Pydantic alias.** Core models are `pydantic.BaseModel` subclasses and
   Pydantic's own JSON handling is the mechanism. AS2 is a JSON format and
   follows JSON naming convention, so the two spellings differ; that difference
   is carried entirely by `validation_alias` / `serialization_alias` on the
   field. Core code MUST NOT type an AS2 spelling — it types `in_reply_to`,
   never `inReplyTo`.

   No parallel core-only naming scheme is built. YAGNI: the aliases already
   provide the separation. How a core implemented in another language would
   handle this is out of scope for this decision.

   **Amended during #3487: the aliases are *derived*, not enumerated.** As first
   written this detail said the spelling is carried "entirely by
   `validation_alias` / `serialization_alias` on the field", i.e. one hand-written
   alias per field. That was built and then changed, for a measured reason:
   `pydantic.alias_generators.to_camel` produces the correct AS2 property name for
   27 of 30 real field names, and the three it misses (`id_`, `type_`, `context_`)
   are trailing-underscore fields that already carry explicit aliases and always
   will — `@context` cannot come from any generator.

   Enumerating therefore buys nothing and costs the fields nobody remembers:
   declaring the generator per class instead of once let four promoted types ship
   `attributed_to` on the wire while their siblings shipped `attributedTo`, which
   is invisible until a peer cannot read the payload. So the generator is declared
   once on `CoreObject` and inherited, and what keeps it honest is a closed-world
   test on the projected key set
   (`test_promoted_core_classes_are_exactly_as2_representable`) rather than the
   declaration site. ARCH-12-003 and ARCH-20-001 both forbid this mechanism and
   are annotated; #3578 owns their rewrite.
3. **The 27 paired `as_*` domain classes are deleted.** Message-shape classes
   name core classes in their slots: `object_: VulnerabilityReport`,
   `target: VulnerabilityCase`.

   **Implication, stated deliberately because it is a real new constraint:** a
   core class that can appear in a message slot MUST be exactly
   AS2-representable. Every field it carries must have a valid AS2 property
   spelling, and it MUST NOT carry a field that cannot go on the wire. This
   constrains future core modelling and is accepted. It does **not** extend to
   core classes that never appear in a message — the 23 with no wire
   counterpart (dead-letter records, the role and lifecycle participant
   subclasses, pending-queue entries) are unconstrained by AS2.
4. **The shared root is deleted.** `as_Base` gets its own root carrying the AS2
   envelope fields. Core has **two** roots: a minimal record base (`id`,
   `type`, `name`) for records that are not AS2 objects, such as dead letters,
   and one object root carrying the AS2 object fields, `@context`, and required
   timestamps.
5. **Dimension objects serialize as a bare value.** A dimension object holds
   exactly one data field, `state`; everything else on it is behaviour, and
   behaviour does not serialize. Each dimension gains a whole-model serializer
   and reader so `RmDimension` writes itself as `"START"` and accepts
   `"START"`. With an alias of `rmState`, **the AS2 wire form does not change**,
   so the published ontology and any peer remain valid. This transformation
   belongs on the dimension class, not in a helper or a translator: it is a
   value object stating how it writes itself.
6. **ARCH-22-001 is repealed and replaced by an allow-list.** Wire MAY import
   `vultron/core/models/` and `vultron/core/states/`. Wire MUST NOT import
   anything else under `vultron/core/` — `behaviors/`, `use_cases/`, `ports/`,
   `services/`, `predicates/`, `scoring/`, `participants/`, `dispatcher.py`,
   `sync_helpers.py`. The rule attaches to the *importing* directory, so
   relocating a file cannot evade it, and it is an allow-list so a new core
   package is forbidden by default. ARCH-01-001 (core MUST NOT import wire) is
   unchanged and remains fully satisfied.
7. **Reading is strict, with unknown fields set aside.** Recognised fields are
   validated strictly and a violation is refused at the edge (ADR-0032).
   Unrecognised fields are set aside before validation, not rejected — AS2 is
   designed to be extended, and refusing on an unknown key would make Vultron
   unable to federate with any implementation that adds a property. Their
   values are already preserved verbatim in the ledger payload snapshot
   (CLP-07-001), so no core class gains a loose "extras" field.
8. **Set-aside fields are reported, and near misses are warnings.** Every
   unrecognised field is noted at `INFO`. A `WARNING` is raised when the field
   matches a known field name or alias on the class being read after
   lowercasing and stripping non-alphanumerics, or when it matches a name the
   project has retired. Fuzzy/edit-distance matching is explicitly **not**
   adopted: it needs a tuned threshold, and AS2 has many two- and three-letter
   field names (`to`, `cc`, `bto`, `bcc`, `id`, `url`, `tag`) within one
   character of each other. The two deterministic checks catch every failure of
   this kind the project has actually had, including #2262.
9. **Object slots hold the whole object, not an ID.** Reading resolves an IRI
   reference to the referenced object; an unresolvable reference is deferred or
   refused. **`rehydrate()` owns that materialisation** — VM-06-007, in
   `vultron/wire/as2/rehydration.py`. It already holds the `DataLayer` the
   resolution needs (VM-06-002), so it resolves the *real* object rather than
   standing a placeholder in for it. Which of *deferred* and *refused* applies
   is read off the declared field type: a slot that admits `str` — every
   `ActivityStreamRef[T]` — can legally hold the IRI, so an unresolvable
   reference is deferred there (VM-06-004); a slot that admits a model and no
   `str` cannot, so an unresolvable reference is refused. The `WireParsePort`
   (#2938) was the other candidate and is rejected: it does not exist, its
   prerequisite #2937 is cancelled below, and its single-method wire→core shape
   carries no store access, so it could only have fabricated placeholders —
   which is the defect, not the fix. Per-class `from_core` fabricated a stub
   `as_Activity` with a *synthesized* actor; that is not reproduced, and the
   reasoning is recorded in `materialise_object_slots` and VM-06-007. See the
   caveat under *Measured evidence*.

   **This is a prototype shortcut, recorded as such.** It defers data
   normalization rather than solving it. A production system would be expected
   to normalize considerably further — references rather than embedded copies,
   backed by a single store, with join tables or dedicated join objects where a
   relationship carries data of its own. We are simply not making that choice
   in the prototype at this time. This detail MUST NOT be read as a permanent
   architectural principle, and MUST be revisited before production.
10. **The AS2 vocabulary and the formal message set stay separate artifacts.**
    AS2 can express more sentences than Vultron needs, and the formal protocol
    over-counts in the other direction — proposing an embargo and proposing a
    revision to one are the same sentence with different start and end states.
    Neither list is a subset of the other. The mapping between them is the
    reconciling artifact, as ADR-0083 already decided. The message-shape
    classes stay in `vultron/wire/`, because they subclass AS2 verbs and are
    therefore the AS2 *encoding* of a message, not the message's identity.

### Consequences

- Good, because the duplication disappears at its source. No pairing table, no
  translators, no shared root to keep aligned, no branch-neutral layer.
- Good, because replacing AS2 becomes cheaper, which is the goal the separation
  was meant to serve. Under the parallel hierarchy a second wire format costs
  roughly 127 new classes and 27 new pairings; under one model it costs one
  read/write module.
- Good, because the wire→core boundary test shrinks from a 20-entry violations
  list plus two ratchet tests plus a goal test plus a declared exemption set,
  to one allow-list test.
- Good, because conflating a wire object with a core object becomes
  structurally impossible for domain types: there is only one class per
  concept.
- Good, because declaring the full AS2 object field set on the core root —
  including fields Vultron does not use, such as `bto`, `bcc`, `icon`,
  `image` — now separates "standard AS2 we ignore" from "field nobody
  recognises", instead of being dead weight.
- Bad, because core classes carry AS2 field aliases, so the domain model is
  visibly shaped by AS2. This is accepted deliberately: 234 of 1535 core fields
  already carry one, so the separation being given up was never real.
- Bad, because it supersedes two accepted ADRs and amends three more, and
  requires changes across seven spec groups.
- Bad, because work has already landed on the superseded plan — PR #3440 merged
  2026-09-20 and created the branch-neutral layer for #2932 — so some recent
  effort is reversed.
- Neutral, because the AS2 wire form is unchanged by this decision. The
  dimension-object change is deliberately designed to keep output identical.

## Migration

**This section is transitional. Delete it once the work has landed** — it
describes the difference between the code as it was when this decision was
taken and the decision above, and that difference stops being useful to a
reader the moment it is closed.

- **Delete 25 of the 27 paired `as_*` domain classes**, and retarget the
  message-shape classes' slots at the core classes.
- **Delete the remaining 2 pairs** (`as_CaseStatus`, `as_ParticipantStatus`).
  Larger than it looks: `as_ParticipantStatus` is referenced across dozens of
  production and test modules — re-measure before scoping rather than trusting a
  figure quoted here (MS-16-001) — and the structural
  blocker is `as_CaseParticipant.participant_statuses: list[as_ParticipantStatus]`
  — deleting it forces `as_CaseParticipant` to change, which cascades into its
  activities, its factories, the FastAPI example routes, and two demo scripts.
  This is migration work, not a step that fits inside a spike.
- **Collapse the rendering port.** `As2WireRenderAdapter.render()` currently
  returns `wire_cls.from_core(obj).model_dump(by_alias=True, exclude_none=True,
  mode="json")`. Once the wire counterpart is gone it is
  `obj.model_dump(by_alias=True, exclude_none=True, mode="json")` plus the
  delivery-supplied `@context` — measured byte-identical for
  `ParticipantStatus`. This requires amending **ARCH-20-003**, which presently
  says the port MUST raise when no wire counterpart exists; under one model a
  missing counterpart is the normal case, not an error.

  **Amended 2026-09-24 (#3490): `@context` comes from the core serializer, not the delivery step.**
  As built, `As2WireRenderAdapter.render()` returns `obj.model_dump(by_alias=True, exclude_none=True, mode="json")` of the `CoreObject` itself, with nothing added at delivery.
  `@context` is emitted by a model serializer on `CoreObject`, and only on a `by_alias=True` dump.
  This deviates from the "delivery-supplied `@context`" above, for three reasons.
  The namespace is supplied in exactly one place (VM-10).
  A `by_alias` dump of any core object is then complete AS2, with no second step to forget.
  A persistence dump, which does not use `by_alias`, still carries no context.
- **Collapse the core root stack from three levels to two.** The middle level
  (`VultronObject`) existed only to keep timestamps optional so the wire half
  could stay lenient (ARCH-12-002); `CoreObject` then re-tightened them. With no
  wire half sharing the root, the middle level has no job.
- ~~**Fix the 73 places under `vultron/core/` that type an AS2 spelling.**~~
  **Done (#3485.)** The real figure is **39** core-*logic* sites across 11 files;
  the rest of the 73 grep hits were alias declarations and prose, which are
  correct and stayed. The fix is a derivation rather than a table:
  `vultron/core/models/wire_keys.py` reads the wire spelling off the field's
  declared alias, so core names the core field and the camelCase is never typed
  and cannot drift.

  `_SNAKE_TWINS` was reduced, not deleted — deleting it would have broken the
  adjudication-patch path (RSH-05-009, CM-18-006). It was two contracts fused
  together, now separated in `vultron/core/behaviors/ledger_patch.py`: the
  RSH-05-013 allow-list of patchable keys, and the stale-twin map that stops a
  consumer reading a value the receiver refused.

  Two behaviour deltas, both in the strict direction and both deliberate.
  `emConsentState` is dropped from the patch allow-list, so an override naming it
  is now refused — no producer emits it and nothing adjudicates consent
  (ADR-0046). And an explicit `{"rmState": None}` now raises instead of falling
  back to the dimension default, which is detail 7's fail-loudly rule; nothing in
  the suite relied on the fallback.

  One convergence worth noting: `CaseStatus.em`/`pxa` now declare
  `serialization_alias="emState"`/`"pxaState"`, so core and `as_CaseStatus` emit
  **identical key sets**. One path changes — `behaviors/status/nodes/case_status.py`
  hand-builds a snapshot by dumping a core `CaseStatus` directly rather than
  through `WireRenderPort`, and that snapshot was carrying the core spelling. It
  was the odd one out among ledger snapshots; it now matches. Every
  port-rendered snapshot is unchanged.
- ~~**Name the owner of ID-to-object materialisation**~~ **Done (#3486.)**
  `rehydrate()` owns it (VM-06-007); detail 9 and the caveat under *Measured
  evidence* both name it. `WireParsePort` (#2938) was rejected on three grounds:
  it does not exist, its own AC-2 requires resolving a counterpart *through the
  pairing registry* — which this ADR cancels — and its single-method shape has no
  store access, so it could only have fabricated placeholders, which is the
  defect rather than the fix.

  The synthesized actor is **declared unnecessary, and was actively wrong.**
  `as_Activity.actor` is required with no default, so a stub built from a bare ID
  had to supply something, and `from_core` had no data layer to ask — so it
  invented `attributed_to or id_`. But `record_activity` records activity by *any*
  participant, so that misattributes every activity the case owner did not
  perform, and the fallback attributes an activity to a *case*, which is not an
  actor at all. `actor` is what semantic dispatch and the AKM-03-001 outbox gate
  both key on. Corroborating: `as_VulnerabilityCase.model_validate({"case_activity":
  ["urn:uuid:a1"]})` raises today, which shows the stub was the only way a case
  with recorded activity could become a wire object — a type-mismatch workaround,
  not a behaviour. The argument is recorded in the `materialise_object_slots`
  docstring, in VM-06-007, and in a test asserting the resolved actor is neither
  the case owner nor the case URI.

  `as_Collection` endpoint slots (`inbox`, `outbox`, `followers`, …) are excluded:
  an actor's inbox is an address, ActivityPub publishes it as a URI, it usually
  belongs to a remote actor, and `as_Actor` already declares a `mode="before"`
  coercion for it.
- ~~**Rename the four misnamed wire classes** to `as_*`.~~ **Done (#3484.)**
  `as_VultronObject`, `as_VultronActivity`, `as_VulnerabilityCaseStub`,
  `as_VultronActorMixin`. The 47 `_XxxActivity` classes are private and
  unambiguous, and stayed.

  Two things worth carrying forward. `WIRE_TYPE_MAP` is keyed on
  `cls.__name__.removeprefix("as_")`, so *adding* the prefix is registry-neutral
  while changing the stem is not — and `VulnerabilityCaseStub` is both a live
  registry key and a published JSON-LD term in `docs/ns/context.jsonld`. And
  `VultronActorMixin` named two different things: the wire class, and the core
  alias `VultronActorMixin = CoreActor`. `test_wire_vocab_naming.py` reported
  zero collisions throughout, because it scans `class` statements and a name
  introduced by assignment is invisible to it. That hole is now closed.
- ~~**Replace the ARCH-22 ratchet** — its 20-entry `KNOWN_VIOLATIONS` set, two
  two-sided tests, `xfail` goal test and declared exemption set — with the
  single detail-6 allow-list test.~~ **Done (#3483.)** `case_states/` and
  `participants/` were classified **forbidden**: despite its name the former
  holds graph-walking and validation behaviour rather than state definitions,
  and the bare enumerations wire legitimately needs already live in
  `vultron/core/states/`. `TYPE_CHECKING`-only imports are exempt generally,
  not by carving out the one file that needed it.
- **Retire ADR-0017 and ADR-0082**, including the forward references from
  `notes/wire-core-boundary.md`, `notes/vocabulary-registry.md`,
  `notes/core-wire-rendering-port.md`, `docs/reference/glossary.md` and several
  spec rationales. (The ratchet test that also cited them is already deleted with
  detail 6.)

## Validation

Detail 5 is the part of this decision that could have failed, so it was
validated before the rest was planned. `ParticipantStatus` is the hardest of the
27 pairs, being one of only two whose fields differ by name rather than by
spelling.

**Acceptance test: the serialized AS2 output is byte-identical to today's.**

**Result: passed.** With the dimension wrapper collapsed and four field aliases
declared, core `ParticipantStatus` produces output identical to
`as_ParticipantStatus` across six state combinations (default, RM-only, vendor,
deployer, consent, all-set), modulo timestamps. Only two keys needed anything
added: a derived display `name`, which moved onto the core class, and
`@context`, which the delivery step supplies by existing design
(`CoreObject.context_` is deliberately `exclude=True` because the JSON-LD
namespace is a transmission concern).

**Amended 2026-09-24 (#3490):** that description of `@context` is historical.
`CoreObject.context_` is still `exclude=True`, but the delivery step does not supply the namespace.
A model serializer on `CoreObject` emits `@context` on every `by_alias=True` dump, using `context_` when one was supplied and the Vultron context otherwise.
A persistence dump without `by_alias` still omits it.
The reasons are recorded in the amendment to "Collapse the rendering port" under Migration.

The spike surfaced two things worth recording, both of which are this ADR's own
argument appearing unprompted.

**First: three inconsistent copies of one rule.** `as_CaseStatus.from_core`
already tolerated both the bare and the mapping form of a dimension
(`em_dim.get("state") if isinstance(em_dim, dict) else em_dim`). Its two sibling
before-validators — `as_CaseStatus._migrate_core_dimension_format` and
`as_ParticipantStatus._migrate_core_dimension_format` — accepted only the
mapping form. Given the bare form, the dict-only branch left the key unconsumed,
never set the flat field, and let the state fall back to its initial value
(`RM.START`, `EM.NONE`) **with no error** — the #2262 silent-state-loss pattern,
in two further locations. All three now agree. This is the fourth duplication
ADR-0082 described, found in a place ADR-0082 did not enumerate.

**Second, and larger: persistence currently round-trips core objects through the
wire vocabulary.** `_storable_to_record` in
`vultron/adapters/driven/datalayer_sqlite/crud.py` normalises through
`_NORMALIZE_WIRE_TO_CORE`, and its docstring says that set is "currently
`CaseParticipant` and `ParticipantStatus`". It is not. The set holds **15**
types, including `VulnerabilityCase`, `CaseStatus`, `VulnerabilityReport`,
`EmbargoPolicy`, `CaseLedgerEntry` and all five actor types. So `DataLayer.update`
for a case reconstitutes it as `as_VulnerabilityCase`, walks its nested
`as_CaseStatus` children, and projects back — meaning a plain persistence write
passes through the wire classes and is exposed to every projection gap in them.
That is how an EM state set by a caller was being dropped between
`DataLayer.update` and the stored row.

This is a materially deeper entanglement than the "translation at the boundary"
picture in ADR-0062 and ADR-0082, and it strengthens the case for one model:
under one model there is nothing for `_NORMALIZE_WIRE_TO_CORE` to normalise,
because the stored object and the transmitted object are the same class. The
stale docstring should be corrected independently of this ADR.

The status remains `accepted-provisional` because the details carrying the most
risk are still argued from the measured evidence rather than exercised. Detail 5
was validated by the spike above, and details 2, 6 and 9 gained enforcing tests
when they landed. Details 1, 3, 4, 7, 8 and 10 are not yet exercised — and
detail 3, the deletion of the paired classes, is both the largest remaining piece
and the one the rest depends on.

Ongoing validation:

- `test/architecture/test_wire_core_import_allowlist.py` enforces the detail-6
  allow-list, replacing the deleted wire→core ratchet
- the existing `test/architecture/test_core_no_wire_imports.py`, unchanged
- `test/architecture/test_core_no_as2_spellings.py` asserts no module under
  `vultron/core/` contains an AS2 spelling, covering detail 2
- `test/core/models/test_dimension_bare_serialization.py` holds detail 5,
  including the parity of core and wire AS2 output
- `test/wire/as2/test_rehydration_materialisation.py` holds detail 9's
  materialisation owner

## Pros and Cons of the Options

### One object model; AS2 is a serialization of it

- Good, because it matches the measured evidence: there is one model, not two.
- Good, because it removes the machinery rather than relocating it.
- Bad, because it is the largest change of the four options.

### Relocate the shared root to a branch-neutral layer (#2933)

- Good, because it is incremental and already planned and scoped.
- Bad, because it cements a decision whose premise ADR-0082 already removed.
- Bad, because it requires moving `CORE_TYPE_MAP` or inventing a registration
  seam, since `VultronObject.__init_subclass__` writes to a core registry and a
  branch-neutral module may not import core.

### Two fully independent hierarchies plus a translator

- Good, because it removes the inheritance entanglement with no ambiguity.
- Bad, because it keeps every duplicate class and the translator, which is the
  larger cost, while the measurement shows no semantic difference to translate.

### Adopt a third-party AS2 hierarchy

- Good, because it reduces hand-maintained surface for the pure-AS2 subset.
- Bad, because it introduces a foreign root and does not address the
  duplication, which is the actual problem. Deferred; see #2947.

## More Information

### Measured evidence

Measured on `origin/main` at 55f5ff467. Do not re-derive.

**Population, classified by module rather than by name prefix:**

| | count |
|---|---|
| classes under `vultron/wire/` | 127 |
| of those, *not* named `as_*` | 51 |
| classes under `vultron/core/models/` | 45 |
| `as_*` classes paired to a core class by name | 27 |
| `as_*` classes with no core counterpart | 49 |
| core classes with no wire counterpart | 23 |

The 51 misnamed wire classes (`VulnerabilityCaseStub`, `VultronAS2Object`,
`VultronAS2Activity`, `VultronActorMixin`, and 47 `_XxxActivity` classes) are
the concrete form of the tell-them-apart problem. The first four are renamed to
`as_*` by this decision; the `_XxxActivity` classes are private and
unambiguous.

**The 346 differing fields across the 27 paired classes:**

| share | kind of difference |
|---|---|
| 46.0% | same base type; core adds a validator or makes it required |
| 24.9% | wire declares `Any`; core states the real type |
| 14.5% | core declares `Any`; wire states the real type |
| 10.4% | AS2 inline-or-IRI-or-Link union; `type_` enum vs `Literal` |
| 4.3% | `type_` enum vs `Literal` |

Only two pairs differ by field name rather than spelling:

- `as_CaseStatus` / `CaseStatus` — wire `em_state`, `pxa_state`; core `em`, `pxa`
- `as_ParticipantStatus` / `ParticipantStatus` — wire `rm_state`, `vf_state`,
  `d_state`, `em_consent_state`; core `rm`, `vf`, `d`, `consent`

### Caveat: the measurement covers declared field types, not projection bodies

Stated plainly because the summary above is easy to over-read. The 346-field
analysis compares the **declared type of each field** on the 27 paired classes.
It does *not* measure what the `from_core()` / `to_core()` method bodies do, and
some of them do structural work no alias can express. `as_VulnerabilityCase
.from_core` fabricates objects:

```python
data["case_activity"] = [
    as_Activity(id_=activity_id, actor=core_obj.attributed_to or core_obj.id_)
    if isinstance(activity_id, str) else activity_id
    for activity_id in data.get("case_activity", [])
]
```

A string ID becomes a stub object with a *synthesized* actor. Counting
structural operations across the projection overrides — object construction,
`.to_core()` recursion, ref unwrapping, dimension mapping, list comprehension:
`vulnerability_case` 20, `case_status` 15, `case_participant` 7,
`vultron_actor` 5, `vulnerability_report` 4, `case_reference` 4,
`case_actor` 3, and only `case_ledger_entry` at zero.

Most of it dissolves with the second hierarchy, because it exists only to bridge
two shapes: `.to_core()` recursion into nested children, and
`_scalar_ref_id_or_value` unwrapping a wire `object | Link | str` union into a
core scalar. Both have nothing to do once there is one shape.

**One kind does not dissolve: materialising an object from an ID.** That is
detail 9's rehydration, and per-class `from_core` code is what implements it
today. Detail 9 says slots hold whole objects; it does not say what fills them.
Deleting the projection methods without naming a replacement owner would drop
the behaviour silently — the same failure shape as the two silent-state-loss
bugs the spike found. The candidates were `rehydrate()` (VM-06-001) and the
`WireParsePort` (#2938); **detail 9 above names `rehydrate()`** and VM-06-007
records it.

Surfaced by #3437, which had been filed as a narrow adapter-consolidation
cleanup.

**Core is already AS2-shaped.** 234 of 1535 core model fields carry a
wire-facing alias, including the AS2 backbone: `id`, `type`, `@context`,
`inReplyTo`, `mediaType`, `attributedTo`, `preferredUsername`.

**Core code already types AS2 spellings** in 73 places, including a
hand-written translation table at
`vultron/core/behaviors/case/nodes/lifecycle.py:98` mapping `"rmState"` to
`"rm_state"`, and 21 `by_alias=True` calls under `vultron/core/`. This is the
cleanup detail 2 creates.

**What wire actually reaches into core for today:** 50 imports from
`vultron.core.models`, 14 from `vultron.core.states`, and one
`TYPE_CHECKING`-only reference to the `DataLayer` interface at
`vultron/wire/as2/rehydration.py:36`. No behaviours, no use cases, no handler
logic. And core imports **nothing** from wire — ARCH-01-001 is fully held.

The old rule therefore banned the harmless direction while the harmful coupling
passed through it undetected, as duck-typing: core calling `getattr(obj,
"to_core", None)` at three sites, which no import-based test can see.

**A dimension object holds one field.** `RmDimension.model_fields` is exactly
`["state"]`; the rest of the class is `transition()` and guard predicates. It
already reads a bare string via `field_validator` and writes a bare string via
`field_serializer`. Only the one-key `{"state": ...}` wrapper stands between the
core form and the wire form. There is no stored state requiring backward
compatibility.

### Relationship to other decisions

**Partially supersedes** — recorded as `partially_superseded_by` on both, which
annotates them without retiring them, rather than `superseded_by`, which would.
Both retain `status: accepted` deliberately: this ADR is
`accepted-provisional`, and retiring two accepted decisions on the strength of a
provisional one would overstate what has been established. Flip both to
`superseded` and move them to `docs/adr/archived/` when this ADR reaches
`accepted` — and note that move rewrites roughly 140 references across `docs/`,
`specs/`, `notes/` and `test/`, so it wants to happen once.

- **ADR-0017** — the Option D shared root is replaced. Everything Option B
  contributed and ADR-0017 preserved — `CoreObject`, `CORE_VOCABULARY`, the
  migrated domain types from the #699 chain — survives as *the* model here. Its
  domain/wire separation rationale still reads correctly; only the shared-root
  mechanism does not.
- **ADR-0082** — the diagnosis stands and is the foundation this ADR builds on:
  the four duplications, the measured evidence, and the finding that "zero
  wire→core imports" was unreachable. The *remedy* is replaced — there is
  nothing to pair and nothing to translate once the second hierarchy is gone.
  Item 8 of its Decision Outcome is the specific item reversed here.

**Amends:**

- ADR-0009 — repeals the wire→core prohibition that was never among its six Key
  Rules, and adds the detail-6 allow-list. Rule 6 is unchanged and better
  served.
- ADR-0032 — confirms validate-at-edge, and adds the unknown-field rule that
  ADR-0032 did not state.
- ADR-0036 — dimension objects serialize as a bare value. Governing principles
  1 through 3 are unchanged.

**Unaffected:** ADR-0063 (rendering behind a port), ADR-0083 (the message set
and the AS2 vocabulary are different shapes), ADR-0069 (namespace), ADR-0074
(wire activity immutability).

### Issue dispositions

| issue | disposition |
|---|---|
| #2933 move the shared root to a branch-neutral layer | cancelled — the shared root is deleted |
| #2937 declarative pairing registry | cancelled — nothing to pair |
| #2939 move projection to adapter-side translators | cancelled — no projection code |
| #2942 relocate the semantic extractor | cancelled — it only moved to evade ARCH-22-001 |
| #2944 / #2670 / #2673 the ARCH-22 ratchet and its exemption set | replaced by one allow-list test |
| #2940 `extra="forbid"` on the core branch | re-scoped to the persistence path; inbound is covered by details 7 and 8 |
| #2947 evaluate `activitypubdantic` | unchanged, still deferred |

Generated spec requirements: `SDO-01-004` (detail 5, new). `SDO-03-004`'s
rationale corrected — it claimed dimension fields "serialize as nested dicts",
which is no longer true.

Thirteen requirements carry a `note:` recording that ADR-0099 supersedes,
inverts or repeals their *direction*, while their normative statements stay
true to the current code: `ARCH-01-003`, `ARCH-03-001`, `ARCH-12-001`,
`ARCH-12-002`, `ARCH-12-005`, `ARCH-12-010`, `ARCH-20-002`, `ARCH-20-003`,
`ARCH-21-002`, `ARCH-22-001`, `ARCH-22-003`, `ARCH-23-001`, `ARCH-23-006`.

Annotating rather than rewriting is deliberate. The specs are what
`load-specs` feeds to implementation agents. Rewriting `ARCH-22-001` to permit
wire→core imports while the ratchet test and its 20-entry violation set are
still in the tree would make the corpus contradict both the code and itself,
and would have agents implementing a state that does not exist. Each note says
plainly: this still describes the code, do not implement it as a target. The
normative statements are rewritten when the migration lands.

Two of the thirteen are inversions rather than repeals, and both carry a
prerequisite: `ARCH-20-003` (a missing wire counterpart becomes normal rather
than an error) and `ARCH-23-006` (wire annotations MUST name core classes). The
defect behind `ARCH-23-006` is real and must be re-handled before inverting it —
`VultronValidationError` is not a `ValueError` subclass, so a core-side guard
firing while Pydantic resolves a union escapes the whole operation instead of
being absorbed as a failed union branch.
