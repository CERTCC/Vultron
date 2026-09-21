---
status: accepted-provisional
date: 2026-09-21
deciders: Allen D. Householder
consulted: notes/wire-core-boundary.md, notes/domain-model-separation.md
---

# One Object Model: AS2 Is a Serialization of the Core Model, Not a Parallel Hierarchy

> **Implementation status as of 2026-09-21: decided, not yet built.**
> The decision details below are in the present tense because they state the
> decision, not the state of the code — that is the MADR convention. Nothing in
> them has been implemented. What has to change to get there is in
> [Migration](#migration), which is transitional and should be deleted once the
> work lands. Validation is the spike described under [Validation](#validation).

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
   refused.

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
  Measured, because it is larger than it looks: `as_ParticipantStatus` is
  referenced in **20 production files and 43 test files**, and the structural
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
- **Collapse the core root stack from three levels to two.** The middle level
  (`VultronObject`) existed only to keep timestamps optional so the wire half
  could stay lenient (ARCH-12-002); `CoreObject` then re-tightened them. With no
  wire half sharing the root, the middle level has no job.
- **Fix the 73 places under `vultron/core/` that type an AS2 spelling**,
  including the hand-written table at
  `vultron/core/behaviors/case/nodes/lifecycle.py:98` mapping `"rmState"` to
  `"rm_state"`, and review the 21 `by_alias=True` call sites there.
- **Rename the four misnamed wire classes** to `as_*`:
  `VulnerabilityCaseStub`, `VultronAS2Object`, `VultronAS2Activity`,
  `VultronActorMixin`. The 47 `_XxxActivity` classes are private and
  unambiguous, and stay.
- **Replace the ARCH-22 ratchet** — its 20-entry `KNOWN_VIOLATIONS` set, two
  two-sided tests, `xfail` goal test and declared exemption set — with the
  single detail-6 allow-list test.
- **Retire ADR-0017 and ADR-0082**, including the forward references from
  `notes/wire-core-boundary.md`, several spec rationales, and the docstring of
  `test/architecture/test_wire_no_core_model_imports.py`.

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

The status remains `accepted-provisional` because detail 5 is the only detail
validated by code. Details 1 through 4 and 6 through 10 are argued from the
measured evidence but not yet exercised.

Ongoing validation:

- one architecture test enforcing the detail-6 allow-list, replacing
  `test/architecture/test_wire_no_core_model_imports.py`
- the existing `test/architecture/test_core_no_wire_imports.py`, unchanged
- a test asserting no module under `vultron/core/` contains an AS2 spelling,
  covering detail 2

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

**Supersedes:**

- ADR-0017 — the shared-base two-branch hierarchy. Its Option B (independent
  hierarchies) was abandoned for the `from_core()`/`to_core()` protocol, which
  ADR-0082 then forbade.
- ADR-0082 — the pairing registry and adapter-side translators. Its problem
  statement stands; its mechanism is unnecessary once there is one model.

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

Generated spec requirements: to be amended in ARCH-01, ARCH-03, ARCH-12,
ARCH-20, ARCH-21, ARCH-22 and ARCH-23 (`specs/architecture.yaml`), and in
`specs/status-dimension-objects.yaml` for detail 5.
