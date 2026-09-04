---
title: "Message Type Reference: Formal Shorthands, AS2 Wire Forms, and the Mapping Between Them"
status: active
description: >-
  Design guidance for the consolidated per-message-type reference pages: why the
  formal message set and the AS2 wire vocabulary are different shapes, how the
  many-to-many mapping is rendered, and where the fault and acknowledgement
  mechanisms diverged from their specified form.
related_specs:
  - specs/message-semantics-mapping.yaml
  - specs/vultron-as2-mapping.yaml
  - specs/diataxis-requirements.yaml
  - specs/project-documentation.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/case-state-model.md
  - notes/diataxis-framework.md
  - notes/documentation-strategy.md
  - notes/status-dimension-objects.md
  - notes/sync-ledger-replication.md
  - notes/participant-embargo-consent.md
---

# Message Type Reference: Formal Shorthands, AS2 Wire Forms, and the Mapping Between Them

Source: IDEA-605. ADR: [ADR-0083](../docs/adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md).

## The core fact: the two message sets are different shapes

Vultron has two message vocabularies, and they do not correspond one-to-one.

- The **formal message set** (`docs/reference/formal_protocol/messages.md`) is
  28 shorthand symbols, partitioned by *which state machine* the message belongs
  to: RM `{RS,RI,RV,RD,RA,RC,RK,RE}`, EM `{EP,ER,EA,EV,EJ,EC,ET,EK,EE}`,
  CS `{CV,CF,CD,CP,CX,CA,CK,CE}`, General `{GI,GK,GE}`.
- The **AS2 wire vocabulary** is the `SEMANTIC_REGISTRY`
  (`vultron/semantic_registry/`), whose entries pair an `ActivityPattern` with a
  `MessageSemantics` value, an event class, a use case, and a phrase.

The mapping between them is **many-to-many in both directions**, and roughly
half the wire vocabulary has no formal counterpart at all. Do not assume a
shorthand and a wire activity are interchangeable names for one thing; that
assumption is what produced the MSM-03 defect described below.

`specs/message-semantics-mapping.yaml` (MSM) is the normative bridge. Read it
before writing anything that claims a shorthand maps to a wire form.

### Collapses: many shorthands, one wire activity

| Shorthands | Single wire activity | Discriminator |
|---|---|---|
| `CP` `CX` `CA` | `Add(CaseStatus)[target=VulnerabilityCase]` | `as_CaseStatus.pxa_state` |
| `CV` `CF` | `Add(ParticipantStatus)[target=CaseParticipant]` | `as_ParticipantStatus.vf_state` |
| `CD` | `Add(ParticipantStatus)[target=CaseParticipant]` | `as_ParticipantStatus.d_state` |
| `EV` `EJ` `EC` | folded into `EP` / `ER` / `EA` respectively | context, not structure |
| `RI` `RV` `RD` `RA` `RC` | *also* `Add(ParticipantStatus)`, via `rm_state` | payload, parallel to the dedicated report activities |

The last row is the one that surprises people. RM state changes have **two**
wire expressions: the dedicated report-scoped activity
(`Accept(Offer(Report))` = `RV`, `TentativeReject(...)` = `RI`,
`Reject(...)` = `RC`) *and* the `rm_state` field of a participant-status
broadcast. `RA` and `RD` additionally appear as case-shaped activities
(`Join(VulnerabilityCase)` and `Ignore(VulnerabilityCase)`), because engaging or
deferring is a case-participation decision rather than a report-validity
judgment (MSM-01-005 for `RA`, MSM-01-004 for `RD`).

### Expansions: one shorthand, many wire activities

| Shorthand | Wire activities |
|---|---|
| `EP` | `create_embargo_event`, `add_embargo_event_to_case`, `invite_to_embargo_on_case`, `announce_embargo_event_to_case` |
| `GI` | `create_note`, `add_note_to_case`, `remove_note_from_case`, and the actor-suggestion handshake (`offer_actor_to_case`, `offer_case_participant`, ±accept/reject) |

`GI`'s example list in `messages.md` explicitly includes "suggesting a potential
Participant to be added to a case", so actor suggestion is a `GI` expansion —
**not** case management. Filing it under case management is a recurring
mis-classification.

**The `Create(X)` + `Add(X → Y)` split is itself an expansion with no formal
counterpart.** Every object gains two activities: one to mint it, one to attach
it. The formal protocol models neither. `docs/howto/activitypub/activities/status_updates.md`
already worries about this in prose ("Create *then* Add vs Create with a
Target"); that discussion is Explanation and belongs in `docs/topics/`.

### No formal counterpart at all

Roughly half the registry is case and roster mechanics the formal protocol never
modelled as messages: case lifecycle, participant roster, invitations, role
delegation (ADR-0039), ownership transfer (ADR-0053), case proposal (ADR-0023),
and ledger replication (SYNC). Two of these are **not** case management and
should not be documented as such:

- **Case proposal** is *pre-case* bootstrap. No case object exists yet.
- **Ledger replication** is the substrate that *carries* other messages. It is
  not itself a protocol message.

`unknown` and `unknown_unresolvable_object` are dispatcher fallbacks, not
message types. Exclude them from message-type reference material.

## The mechanisms that evolved rather than went missing

MSM currently records `RE`, `EE`, `CE`, `EK`, and `CK` as having "no AS2 wire
representation." That is true *per shorthand* and misleading *per purpose*: the
work those shorthands describe is done, by mechanisms partitioned on a different
axis. Do not read those MSM entries as "unimplemented."

### Faults: partitioned by failure mode, not by state machine

The formal protocol partitions errors by **which model** the bad message
belonged to (`RE`/`EE`/`CE`/`GE`). The implementation partitions by **why it
failed**, which is orthogonal and arguably the better axis:

| Mechanism | Meaning |
|---|---|
| `Create(ProcessingFault)` | received and **not understood** |
| `as:Reject` | received and understood but **declined** |
| `Create(Note)` / `Add(Note → Case)` | some other problem **needing explanation** |

Two consequences for implementers:

- `as:Reject` is **overloaded**. It carries legitimate protocol rejections
  (`close_report`, `reject_invite_to_embargo_on_case`,
  `reject_invite_actor_to_case`, `reject_case_proposal`,
  `reject_case_ownership_transfer`) as well as error semantics. A receiver cannot
  infer "error" from the verb alone. Note that the shorthand `reject_embargo`
  is *not* a registry name — the embargo rejection is
  `reject_invite_to_embargo_on_case`; `reject_embargo` names only the BT and
  factory helpers (`reject_embargo_trigger_bt`, `em_reject_embargo_activity`).
  `reject_case_ledger_entry` is deliberately excluded from this list: it is the
  ledger NAK of MSM-05-002, not an ordinary refusal.
- `docs/howto/activitypub/activities/error.md` depicts a four-way wire taxonomy
  (`RmError`/`EmError`/`CsError`/`GmError` as `as:Reject` discriminated by
  `as:inReplyTo`). **None of those types exist** — not in the ontology, not in
  code. And `ActivityPattern.in_reply_to_`, the discriminator that design needs,
  is declared on the model (`ActivityPattern` is a Pydantic `BaseModel` in
  `vultron/wire/as2/extractor/_pattern.py`) but is set by **zero** registered
  patterns. Do not cite that diagram as describing the wire format. MSM-05-004
  makes this a `MUST NOT` for documentation — note that `error.md` itself has not
  been corrected yet, so the corpus currently violates it.

Beware a name collision: `VultronError` in `vultron/errors.py` is a **Python
exception base class**, unrelated to the wire type of the same name in that
diagram.

### Acknowledgement: cumulative and implicit, not per-message

`RK` is a real wire activity (`Read(Offer(VulnerabilityReport))`, MSM-01-008).
`EK`, `CK`, and `GK` have no per-message equivalent because acknowledgement
moved axis for replicated state: ledger sync acknowledges **cumulatively and
implicitly** via hash-chain continuity.

A participant that receives `Announce(CaseLedgerEntry)` whose `prev_log_hash`
matches its local tail says nothing — the match *is* the acknowledgement. It
speaks up only on a mismatch, sending `Reject(CaseLedgerEntry)`, whereupon the
CaseActor replays all entries after the last accepted hash
(`RejectLedgerEntryReceivedUseCase`, `vultron/core/use_cases/received/sync.py`).

This is negative acknowledgement with gap-fill replay — structurally closer to
TCP's cumulative ACK/SACK than to a per-message positive ack. Adding per-message
`EK`/`CK` on top would be redundant for ledger-carried state.

## Page architecture

Reference pages live in `docs/reference/messages/`. Formal-model pages are keyed
on the **shorthand**; the remainder are keyed on the **wire activity**, because
no shorthand exists to key them on.

| Page | Keyed on | Covers |
|---|---|---|
| `index.md` | — | Bidirectional mapping overview; how to read collapse/expansion |
| `rm.md` | Shorthand | `RS RI RV RD RA RC RK RE` |
| `em.md` | Shorthand | `EP ER EA EV EJ EC ET EK EE` |
| `cs.md` | Shorthand | `CV CF CD CP CX CA CK CE` |
| `general.md` | Shorthand | `GI GK GE` |
| `faults_and_acknowledgements.md` | Mechanism family | The fault trichotomy; the acknowledgement evolution |
| `case_management.md` | Wire activity | Lifecycle, roster, invitations, role delegation, ownership transfer |
| `case_proposal.md` | Wire activity | Pre-case bootstrap (ADR-0023) |
| `ledger_replication.md` | Wire activity | SYNC substrate |

Each page carries, per message type: protocol role and triggering transition,
the wire activity that conveys it, the discriminating payload field where the
mapping is a collapse, a rendered example, and links to the how-to guide and the
formal transition table.

Every mapping row carries a **status**: `implemented`, `collapsed-into-X`,
`expanded-into-X`, or `evolved-to-X` (for the fault and acknowledgement cases
above). Reference material states what is true, including divergence from the
normative set — see DF-05-003 and DF-05-004.

### One primary page per entry, not one page per entry

MSM-06-002 designates a **primary** page per `SEMANTIC_REGISTRY` entry rather
than requiring each entry to appear on exactly one page, because the collapse
inventory above makes the stricter rule unsatisfiable. The entries that
legitimately need a second home:

| Entry | Primary page | Also appears on | Why |
|---|---|---|---|
| `add_participant_status_to_participant` | `cs.md` | `rm.md` | `vf_state`/`d_state` carry CV/CF/CD; `rm_state` carries the RM ladder |
| `close_report` | `rm.md` | `faults_and_acknowledgements.md` | `RC` on the RM page; an ordinary `as:Reject` on the faults page (MSM-05-003) |
| `reject_case_ledger_entry` | `ledger_replication.md` | `faults_and_acknowledgements.md` | The ledger NAK is both the SYNC mechanism and the acknowledgement story (MSM-05-002) |

Build the #2998 ratchet against the primary designation. Reading MSM-06-002 as
"one page, full stop" will make it look unimplementable.

### Mapping tables are rendered, never hand-written

Render the tables at build time from the MSM spec registry joined against
`SEMANTIC_REGISTRY`, following the `docs/reference/specs/*.md` →
`vultron/metadata/specs/docs_render.py` pattern. Hand-written tables rot: the
orphaned JSONs under `docs/reference/examples/` and the failing `markdown_exec`
example blocks tracked by #2904 are what that rot looks like after a couple of
years.

MSM-06-002 requires a ratchet test asserting every `SEMANTIC_REGISTRY` entry
reaches its designated primary reference page, so a new registry entry cannot be
added without being documented or explicitly exempted. **That ratchet is
implemented in `test/architecture/test_msm_coverage_ratchet.py`**, landed in
PR 2998.

## Diátaxis: these pages are an extraction, not a new surface

`docs/howto/activitypub/activities/` is a **partial collapse** — it runs against
DF-01-003 (pages SHOULD NOT combine multiple Diátaxis content types; where a
combined view is unavoidable, the parts MUST be separated and each MUST link to
the canonical page of its own type). These pages neither separate nor link, so
they do not qualify for the escape clause. Each page mixes three quadrants:

| Content | Actual quadrant | Destination |
|---|---|---|
| Design rationale, why-this-verb, alternatives weighed, activity-graph diagrams | Explanation | `docs/topics/` |
| AS2 encoding facts, rendered JSON examples | Reference | `docs/reference/messages/` |
| `!!! example "Try it: vultron-demo <scenario>"` blocks | How-to | stays, retitled "How to …" |

Diagnostic evidence: the titles are noun phrases ("Status Updates and Comments",
"Acknowledging Other Messages") where DF-04-003 and the framework require
"How to [Action]"; the pages contain no imperatives or steps; `acknowledge.md` is
almost entirely design rationale and passes the bath test; and nearly every page
carries `{% include-markdown "not_normative.md" %}`, which is itself a signal the
author knew the content was discursive. The two pages without that banner are
`error.md` and `acknowledge.md` — which is not counter-evidence, since those are
the two whose content is *least* task-shaped. `error.md` additionally documents a
wire format that was never built (see above), and `acknowledge.md` is the
bath-test example.

So the reference pages are the Reference half of un-blurring an existing
collapse. Treating them as a fourth parallel surface would deepen the collapse
instead of resolving it.

## Examples are rendered at build time

Use `markdown_exec` blocks calling `vultron.wire.as2.vocab.examples.vocab_examples`.
Build-time rendering cannot go stale.

Two patterns are easy to confuse. `docs/reference/specs/protocol.md` is the
exemplar for the **mapping tables** — a thin `markdown_exec` shell over
`vultron.metadata.specs.docs_render.render_for_kind`. It does *not* render wire
examples. For the **examples** themselves, follow the `_*.md` partials under
`docs/howto/activitypub/activities/` and `docs/howto/activitypub/objects.md`,
which are the pages that actually call `vocab_examples`.

Two prerequisites:

- **#2904 blocks this.** Every `markdown_exec` example block currently fails from
  a single root cause (frozen-model assignment in `_strip_published_udpated`). Any
  page rendering examples this way inherits the failure until that lands.
- `docs/reference/examples/*.json` are retained as downloadable artifacts, but
  the generator's hardcoded relative output path
  (`../../docs/reference/examples` in `vocab_examples.main()`) must be fixed and
  a regeneration check added, or they will silently diverge from the rendered
  examples again.

## MSM-03 defect: `CV`/`CF`/`CD` were mapped to the wrong object

MSM-03-001, MSM-03-002, and MSM-03-003 asserted — at `MUST` / `kind: protocol` —
that `CV`, `CF`, and `CD` dispatch as `ADD_CASE_STATUS_TO_CASE` with wire form
`Add(CaseStatus)[target=VulnerabilityCase]`, and that the `CaseStatus` payload
"encodes the `vendor_aware` / `fix_ready` / `fix_deployed` state flag."

All three claims were wrong:

- `as_CaseStatus` carries only `em_state` and `pxa_state`. There are no
  `vendor_aware`, `fix_ready`, or `fix_deployed` fields on it, in any spelling.
- The VF and D dimensions live on `as_ParticipantStatus` as `vf_state: CS_vf`
  and `d_state: CS_d`, so the correct semantic is
  `ADD_PARTICIPANT_STATUS_TO_PARTICIPANT` and the correct wire form is
  `Add(ParticipantStatus)[target=CaseParticipant]`.
- Per ADR-0075, this is necessary, not incidental: VF is **vendor-scoped** and D
  is **deployer-scoped**. **There are no case-level VF/D states at all** — those
  dimensions are always participant-specific. A case-level status cannot express
  *which* vendor is aware, which is the entire purpose of the VF dimension in
  MPCVD.

The last point is worth stating as a standing rule, because the CS model's own
name invites the error. The CS "case state" hypercube mixes two scopes:

| Dimensions | Scope | Wire home |
|---|---|---|
| `V` `F` `D` | **Participant** — one per (actor × case) | `as_ParticipantStatus.vf_state` / `.d_state` |
| `P` `X` `A` | **Case** — one per case | `as_CaseStatus.pxa_state` |

`notes/case-state-model.md` § `CaseStatus` / `ParticipantStatus` already records
this, including that `vf` and `d` are `None` for non-VENDOR and non-DEPLOYER
participants and that this is *structurally enforced*. So MSM-03 did not merely
lack an update — it asserted, normatively, the opposite of an invariant the
domain model enforces.

Cause: MSM-03 predates the VF/D split (ADR-0075) and the dimension-object
decomposition (ADR-0036), and its group description generalized "All CS
shorthands (CV through CA) share the `ADD_CASE_STATUS_TO_CASE` semantic" onto
entries that should have diverged. An implementer following it faithfully would
have dropped the vendor identity — see AGENTS.md § "'CaseActor MUST …' Is Often a
Specification Error" for the same failure mode.

**Guidance:** when a spec group description asserts a property of "all" its
members, check each member against the code before relying on the
generalization. Group descriptions are written once and rarely revisited when one
member's behaviour changes.
