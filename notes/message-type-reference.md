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
  - specs/semantic-extraction.yaml
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

**Why `GI` expands at all, which nothing recorded before #3456.** `GI` was a
*placeholder*, and it is defined negatively: messages that no formal state machine
tracks but that participants need in order to coordinate. The formal protocol
deliberately did not attempt to enumerate them, so it lumped them together under one
shorthand. Building this prototype surfaced specific needs inside that category, and
where a need turned out to be a recognizable communication pattern that existing AS2
vocabulary could already express, it was split off and given its own activity. The set
split off so far is enumerated in MSM-04-001 and MSM-04-002 — read it there rather than
restating a count here, which would drift the moment another is split off (MS-16-002).

Two consequences follow, and both matter when writing about these activities:

- **The list is open, not a finished decomposition.** A further coordination need that
  matches available AS2 vocabulary can be split off the same way. Do not write as though
  the current set is complete.
- **Citing `(GI)` does not identify an activity.** It says only "this is one of the
  non-state-change messages", which is equally true of six others. Name the act in plain
  language and cite `GI` once per page as the umbrella, rather than after each activity.

**The `Create(X)` + `Add(X → Y)` split is itself an expansion with no formal
counterpart.** Every object gains two activities: one to mint it, one to attach
it. The formal protocol models neither, so an implementation that collapses the
pair loses no protocol-level information. That reconciliation now lives in
`docs/topics/activity_vocabulary_design.md`, extracted from the prose that used
to worry about it in `status_updates.md`, `manage_participants.md`,
`invite_actor.md`, and `initialize_case.md` (#3002).

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

### Three names, and which one the reader gets

Any given activity can be named three ways, and they are not interchangeable:

| Layer | Example | Answers |
|---|---|---|
| Formal protocol message | `RV` — "Report Valid" | *What protocol act is this?* |
| Prototype class or pattern | `RmValidateReport` | implementation-level restatement of the same act |
| AS2 wire form | `Accept(Offer(VulnerabilityReport))` | *What JSON goes on the wire?* |

**The semantics are not recoverable from the wire form.**
`Accept(Offer(VulnerabilityReport))`, `TentativeReject(Offer(VulnerabilityReport))` and
`Reject(Offer(VulnerabilityReport))` are *valid*, *invalid* and *closed*, and nothing in
the wire form says which. Replacing a protocol name with its wire form therefore deletes
a layer rather than translating one — the mistake #3456 was originally filed to make.

Reader-facing docs pair the protocol layer with the wire layer and omit the prototype
layer entirely: **`<semantic name>` is implemented in ActivityStreams as `<wire form>`**,
then the steps, then the JSON. This is specified as DF-09-010, and recorded as a
corollary of ADR-0083 under "Which name the reader gets" — the two vocabularies being
different shapes is exactly why the reader needs both names. Which semantic name to use
depends on how the shorthand relates to the wire form, which `MappingStatus` already
records:

| `MappingStatus` | Semantic name to use |
|---|---|
| `direct` | The formal message name and its code — "Report Valid (RV)" |
| `collapse` | All the formal names the wire form carries, stated together once, plus the field that selects between them |
| `expansion` | Plain language per act; cite the umbrella code once per page, never per activity |
| `none` | Plain language, taken from the heading `docs/reference/messages/` already gives it |

Two shapes need care beyond the table. `RA`/`RD` name the *report* while their wire verbs
(`Join`/`Ignore(VulnerabilityCase)`) name the *case*: state the act and its consequence
separately, because joining the case is what you do and the RM transition is what follows
(MSM-01-004, MSM-01-005). And `Leave(VulnerabilityCase)` is the canonical RM closure per
ADR-0050 yet has no formal name at all, while `RC` is bound to
`Reject(Offer(VulnerabilityReport))` — say so rather than presenting the pair as tidy.

### The prototype name survives as an identifier, not as prose

An activity is declared twice — as a class in `vultron/wire/as2/vocab/activities/`
and as an `ActivityPattern` in `vultron/wire/as2/extractor/_instances.py` — and
the two names often differ. `_CreateStatusForParticipantActivity` is
`CreateParticipantStatusPattern`. Some activities have only one of the two:
`CreateNote` is a pattern with no class, because a note is minted with a bare
`as:Create` rather than a Vultron subclass. Neither list is a superset.

Those names are still what identifies an activity to the tooling, so they remain the
mermaid **node id** — an edge handle that is never rendered — while the node *label*
carries the reader-facing pair. The pairing ratchet
(`test/architecture/test_docs_activity_verbs.py`) reads the id and rejects a name in
neither list, which is how `CreateStatus` — a plausible-looking name belonging to no
system — was caught. It also checks that the label's wire-form line is the form the
registered pattern actually produces. Prose that merely mentions a name is left alone;
only a `subgraph as:Verb` membership claim is checked, because declaring a name there
asserts the activity exists.

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
- `docs/howto/activitypub/activities/error.md` previously depicted a phantom
  four-way wire taxonomy (`RmError`/`EmError`/`CsError`/`GmError` as `as:Reject`
  discriminated by `as:inReplyTo`). **None of those types ever existed** — not in
  the ontology, not in code. That diagram has been removed and `error.md` now
  describes the correct fault trichotomy (PR #3215, issue #3005). The
  discriminator field `ActivityPattern.in_reply_to_` has also been removed from
  the model — it was declared but used by zero registered patterns. MSM-05-004
  remains a `MUST NOT` against citing the phantom taxonomy. Do not cite the old
  diagram as describing the wire format.

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
CASE_MANAGER replays all entries after the last accepted hash
(`RejectLedgerEntryReceivedUseCase`, `vultron/core/use_cases/received/sync.py`).

This is negative acknowledgement with gap-fill replay — structurally closer to
TCP's cumulative ACK/SACK than to a per-message positive ack. Adding per-message
`EK`/`CK` on top would be redundant for ledger-carried state.

## Diátaxis: these pages are an extraction, not a new surface

`docs/howto/activitypub/activities/` was a **partial collapse** — it ran against
DF-01-003 (pages SHOULD NOT combine multiple Diátaxis content types; where a
combined view is unavoidable, the parts MUST be separated and each MUST link to
the canonical page of its own type). Those pages neither separated nor linked, so
they did not qualify for the escape clause. Each page mixed three quadrants, and
each quadrant went to its own tree:

| Content | Actual quadrant | Destination | Status |
|---|---|---|---|
| Design rationale, why-this-verb, alternatives weighed, activity-graph diagrams | Explanation | `docs/topics/activity_vocabulary_design.md` | done (#3002) |
| AS2 encoding facts, rendered JSON examples | Reference | `docs/reference/messages/` | done (#2999, #3001, #3003) |
| Task sequences and the `vultron-demo <scenario>` runs | How-to | stays, retitled "How to …" | done (#3003) |

The How-to half is not just the retitled remainder. Each guide now carries
prerequisites, an ordered activity sequence with conditional branches, a table of
what to verify, and links out to its Reference and Explanation counterparts — and
nothing else. The wire examples left with the `_*.md` partials that rendered them.

`ledger_replication.md` was retired rather than reshaped, because every sentence
on it described a pattern or a factory and none of it named an action a reader
takes — ledger fan-out is automatic. Apply that test rather than the page's
directory when deciding whether a how-to page has a task in it.

The Explanation half landed as a single page rather than several, because the
rationale is one argument: ActivityStreams supplies the verbs, so every Vultron
choice is either a verb selection, a decision not to mint a type, or a decision
that a distinction the wire draws has no protocol counterpart. Splitting it per
source page would have separated claims that only make sense together. Domain
rationale that already had a home was cross-linked rather than duplicated —
default-embargo reasoning to `topics/process_models/em/defaults.md`,
ledger-buffering reasoning to `topics/case_lifecycle/case_ledger_sync.md`, and
the Actor/`CaseParticipant` distinction to `reference/activitypub/objects.md`.

Four signals identified the collapse, and they generalize to any tree suspected of
one:

- **Noun-phrase titles in the how-to tree.** "Status Updates and Comments" and
  "Acknowledging Other Messages" name a subject, not a task, where DF-04-003
  requires "How to [Action]".
- **No imperatives and no steps.** A page with nothing for the reader to do is not
  in the Action half of the compass whatever directory it sits in.
- **A page that passes the bath test.** `acknowledge.md` was almost entirely
  design rationale, which is Explanation by definition.
- **A normativity disclaimer.** Nearly every page carried
  `{% include-markdown "not_normative.md" %}`, which is an author saying the
  content is discursive. The banners came off in #3003 for exactly that reason:
  a task guide has nothing to disclaim.

The banner signal inverts where you would expect it to. The two pages *without*
it, `error.md` and `acknowledge.md`, had the least task-shaped content of any —
so read its absence as no evidence either way, not as evidence of task shape.

So the reference pages are the Reference half of un-blurring an existing
collapse. Treating them as a fourth parallel surface would deepen the collapse
instead of resolving it.

## Examples are rendered at build time

Use `markdown_exec` blocks calling `vultron.wire.as2.vocab.examples.vocab_examples`.
Build-time rendering cannot go stale.

Two patterns are easy to confuse. `docs/reference/specs/protocol.md` is the
exemplar for the **mapping tables** — a thin `markdown_exec` shell over
`vultron.metadata.specs.docs_render.render_for_kind`. It does *not* render wire
examples. For the **examples** themselves, follow `docs/reference/messages/*.md`
and `docs/reference/activitypub/objects.md`, which are the pages that call
`vocab_examples`. Since #3003 they are the only ones that do — a rendered wire
example in the how-to tree is a collapse re-forming.

A new example function needs a matching `obj_to_file` call in
`vocab_examples.main()` or `test_vocab_examples_current.py` fails on the file-list
mismatch. Note that the generator randomizes IDs and timestamps on every run, so
running it in place rewrites every committed artifact: generate into a temp
directory and copy across only the files you added.

**An example must be dispatchable, and "well-formed" does not imply it.** Set the
discriminator fields the activity's `ActivityPattern` requires — `object_`,
`target_`, `context_` — and note that `ActivityPattern` has **no `origin_`
field**, so `origin` is never consulted for dispatch no matter how well it reads.
`test/architecture/test_vocab_examples_dispatchable.py` is the ratchet: every
example activity must match exactly one registered pattern. It found three examples
that matched none (#3438, #3439, #3433), each rendered on a reference page and each
committed as a JSON artifact, because the two pre-existing gates ask only whether
an example *executes* and whether its *filename* is committed — never whether a
receiver could route it.

Its collector is deliberately permissive about shape, because both narrower rules
had already hidden a target: requiring zero *parameters* rather than zero
*required* parameters skipped the four `report.py` examples that take a defaulted
`verbose` (`submit_report` among them), and requiring `as_TransitiveActivity`
rather than `as_Activity` skipped `choose_preferred_embargo`, an `as_Question`. A
gate that silently resolves fewer targets than it claims is the false-clean signal
DF-09-009 exists to forbid, so the collected count is itself asserted.

The generator's output path is now resolved from the file's own location
(`Path(__file__).parents[5]`), so it works regardless of the caller's working
directory. A drift check in `test/architecture/test_vocab_examples_current.py`
fails when the committed JSON file list diverges from what the generator produces
(#3004). The `markdown_exec` frozen-model bug that blocked all example blocks was
fixed in #2904.
