---
title: AS2 Vocabulary Alignment — Decisions to Build
status: active
kind: plan
tracks:
  - "#6238"   # epic: AS2 vocabulary alignment (wire-delivery, vocabulary-extensions)
  - "#3937"   # epic: multi-case operations (split, merge)
  - "#2567"   # epic: scope decisions for speculative protocol additions
  - "#5414"   # epic: vocabulary extensions
  - "#1092"   # epic: federated multi-org deployment
  - "#5410"   # epic: shared case history
  - "#6242"   # split carries participants and things
  - "#6243"   # consent as an agreed end date (provisional)
  - "#3701"   # merge spec; wire form recorded as a comment
  - "#6244"   # Invite slots; stub as preview
  - "#6245"   # origin and inReplyTo
  - "#6246"   # embargo end as Update
  - "#6253"   # JSON-LD terms and check
  - "#6247"   # ledger and status histories as ordered collections
  - "#6254"   # Refuse(Reject)
  - "#6248"   # instrument, generator, tag
  - "#6249"   # CaseReference holds a Link
  - "#6250"   # Update forms; dead REMOVE_NOTE path
  - "#6251"   # approvals as Offer of the act
  - "#6252"   # TentativeAccept and Undo withdrawal
  - "#5132"   # vulnerability items and references on a case (PR #6262)
  - "#5130"   # epic: Vultron cases and CSAF 2.1 documents translate
  - "#5089"   # fetchable ledger (deferred)
  - "#5090"   # epic: peers can fetch every object, actor and collection
  - "#6255"   # CASE_MANAGER relocation (deferred)
  - "#6256"   # Flag and case moderation (deferred)
  - "#5133"   # TLP markings (deferred)
  - "#6257"   # preview beyond the stub (deferred)
  - "#6258"   # end-date poll (deferred)
  - "#6259"   # concern: rebuilt replies
  - "#6260"   # concern: Create(CaseParticipant) target
  - "#6295"   # Create(CaseParticipant) drops target, keeps context
  - "#6261"   # concern: stale Offer(EmbargoEvent) payload
  - "#6293"   # idea: owner's removal and reinstatement requests name the Actor
description: >
  Decisions from a review of the wire protocol against the full ActivityStreams 2.0
  vocabulary: which AS2 verbs and properties say a CVD sentence more naturally than
  what the code sends today, and what each change touches. One section per tracked
  issue; each section is self-contained so a build agent needs nothing else.
related_specs:
  - specs/case-management.yaml
  - specs/case-ledger-processing.yaml
  - specs/embargo-policy.yaml
  - specs/em-behavior.yaml
  - specs/semantic-extraction.yaml
  - specs/message-semantics-mapping.yaml
  - specs/sync-ledger-replication.yaml
  - specs/case-proposal.yaml
  - specs/message-validation.yaml
  - specs/vultron-as2-mapping.yaml
  - specs/received-status-handling.yaml
  - specs/csaf-report-content.yaml
  - specs/vocabulary-model.yaml
  - specs/case-bootstrap-trust.yaml
  - specs/vultron-protocol-spec.yaml
  - specs/architecture.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/activitystreams-state-update.md
  - notes/vocabulary-registry.md
  - notes/call-out-configuration.md
  - notes/selective-disclosure.md
relevant_packages:
  - vultron/wire/as2
  - vultron/semantic_registry
  - vultron/core/behaviors
  - vultron/adapters/driven
  - vultron/metadata/wire_context
---

# AS2 Vocabulary Alignment — Decisions to Build

The lasting rules these decisions rest on are in
[activitystreams-semantics.md](activitystreams-semantics.md) § "Choosing AS2 Terms".
This note holds the changes those rules imply for today's code. Each `##` section
below names its tracked issue, and the issue links back here.

Section format: **Decision**, **AS2 basis** (quoted from the W3C Vocabulary
`VOC`, Core `CORE`, the Primer, or the `w3c/activitystreams` errata and issues),
**Today** (where the code and specs stand), **Touches** (specs, ADRs, code), and
**Open for planning**.

Pre-1.0, every change here replaces the old wire form outright: no second accepted
form and no compatibility shim (one version only until 1.0).

---

## Split Carries Participants and Things

Issue: #6242.

**Decision.** A case split may carry content from parent to child, item by item, at
the splitter's choice:

- An item that leaves the origin is `Move(x, origin=<parent>, target=<child>)`, e.g.
  vul2's `VulnerabilityItem` goes to the child.
- An item kept in both is `Add(x, origin=<parent>, target=<child>)`, e.g. the
  original report that describes both vuls.
- A participant is carried as its **actor**: `CaseParticipant` is per (case, actor),
  so the child gets a new participant record and the parent's record closes (Move)
  or stays (Add). The `Move`'s `result` names the new and closed records.
- The Case Owner decides by fiat; the moved actor is notified, not asked. A
  Coordinator may still choose a consent-first sequence with existing verbs
  (Invite to the child, Accept, Leave the parent); nothing is built for it.
- `Move` is admissible only between cases related by a split or merge
  (`parent_cases` / `child_cases`), at any time, and only while one Owner holds both.
  After the child's ownership is transferred, the parent's Owner can no longer move
  anything into it. Any other pair of cases uses `Add` (and `Remove`) as separate
  acts. Putting an actor into a second case is `Add`.

PR #6262 (issue #5132) proposes ADR-0187 and the CM-34 requirements, which rename
`VulnerabilityItem` to `VulnerabilityItem`; this note uses the proposed name
throughout.

**AS2 basis.** VOC Move: "the actor has moved object from origin to target". VOC
Add notes: "The origin can be used to identify the context from which the object
originated"; Ex 13 adds with an `origin` and nothing says the object leaves it. AS2
has no Copy, Split, Merge, Clone or Replace verb.

**Today.** ADR-0125 (accepted) copies nothing into the child but a new embargo with
the parent's end time: "No report, note, ledger entry, Participant, case status,
vulnerability record, or case reference is copied." CM-32 specifies the split; it
is not implemented (#4242).

**Touches.** A new ADR superseding ADR-0125's "nothing transfers" part; CM-32;
the consent carry-over in § "Embargo Consent Is an Agreed End Date".

**Open for planning.** Whether each carried item is its own ledger entry in both
ledgers (a Move is a removal in one and a seat in the other) and how the two stay
consistent; the sender rule for a later cleanup Move.

---

## Embargo Consent Is an Agreed End Date

Issue: #6243.

**Status: provisional.** The user stated this as design in progress, not settled
ground truth. Plan it as an Idea to be grilled before any build.

**Decision (provisional).**

- What a participant consents to is an end date: each participant record holds one
  current value, "agreed to end the embargo at X", or none — not a row per embargo
  id.
- Agreeing to Y replaces X. A participant is covered by an embargo when its agreed
  end date is on or after the embargo's end time. So agreeing to a later Y covers an
  earlier X; agreeing to an earlier Y does not cover a later X. This is the
  shortest-wins rule of the EM formal model (§ "Why the shortest proposal wins")
  applied to consent.
- At a split, the child's new participant record copies the agreed end date from
  the parent's record. The child's embargo starts with the parent's end time, so the
  carried participant is covered without answering. After the split the two
  embargoes evolve independently (the VP-10 family notice rules still apply).

**Today.** CM-18 and ADR-0122 record consent as one row per (participant, register
entry), starting `UNINVITED`, changed only by an answer to that entry.

**Touches.** CM-18, ADR-0122, CM-13, the EM formal model
(`docs/topics/process_models/em/formal_model.md` § "Why the shortest proposal
wins"), § "Split Carries Participants and Things".

**Open for planning.** Whether the change is to the consent model or only to the
split carry-over; what replaces signatory and lapsed reads (CM-18-016); the
interaction with RSVP deadlines (CM-28).

---

## Merge Wire Form

Issue: #3701 (comment).

**Decision.**

- After the merge is accepted, Case2's CASE_MANAGER commits `Update(Case2)` as the
  last entry in Case2's ledger. The updated case carries the merge relation (in the
  `parent_cases` / `child_cases` / `sibling_cases` field the merge spec picks) and a
  frozen marker. The merge offer's `Accept` names that `Update` in `result`.
- Case2's **participants** join Case1 by Invite, as ADR-0105 says, because a merge
  brings counterparties a participant never agreed to coordinate with (unlike a
  split, whose child roster comes from the parent).
- Case2's **things** (reports, vul records, notes) may be carried by
  `Move(x, origin=Case2, target=Case1)` or copied by `Add(x, origin=Case2,
  target=Case1)`, under the Move rule in § "Split Carries Participants and Things".

`Move(Case2, target=Case1)` (ActivityPub account-migration practice) was rejected:
Case2 does not go anywhere, so the sentence would be false. `movedTo` is community
usage and is not in the AS2 context.

**Today.** ADR-0105 (accepted) decides freeze-and-redirect by Owner consent. Merge has
no wire form, message semantic or code.

**Touches.** A merge spec (none exists); ADR-0105 consequences; a received
`Update(VulnerabilityCase)` handler (no `Update` has a received use case today, see
`notes/activitystreams-state-update.md` § "A Received `Update(VulnerabilityCase)` Is
Not Processed").

**Open for planning.** Whether frozen is a property or a terminal case state.

---

## Invites Use the Spec's Slots, and the Stub Is the Case's Preview

Issue: #6244.

**Decision.**

1. Both Invites follow AS2: `object` is what the invitee is invited to, `target` is
   the invitee.
   - Case Invites: `Invite(VulnerabilityCase or reference)[target=Actor]`, replacing
     `Invite(Actor)[target=Case|Stub]`.
   - Embargo Invite: `Invite(EmbargoEvent)[target=Actor]`, adding the `target` it
     lacks (the invitee is only in `to` today).
2. The stub becomes the case's `preview`. The stub Invite's object is a typed case
   reference (ADR-0165 form: `id` and `type` only) carrying
   `preview: VulnerabilityCaseStub{summary, activeEmbargo, …}`. The stub's Vultron
   `caseId` is dropped: the case is named by the reference's own `id`. The full-case
   Invite carries the full case.
3. **A preview is never the case.** Only a full case is a case: no receiver seeds or
   updates a replica from a reference that carries a preview.

**AS2 basis.** VOC Invite: object is the event, target the invitees ("Sally invited
John and Lisa to a party"); issue #619 confirms Invite is the one verb whose `target`
is the person, kept for compatibility. VOC `preview`: "Identifies an entity that
provides a preview of this object." Primer chess example: `Accept(Invite)` whose
`result` is the new game.

**Today.** `vultron/wire/as2/extractor/_instances.py` tells the stub Invite from the
full-case Invite only by the type in `target`, which needs `strict=True`
(`notes/activitystreams-state-update.md` § "Patterns Sharing a Verb and Object Need
a Strict Discriminator"). The stub class is
`vultron/wire/as2/vocab/objects/vulnerability_case.py` (`as_VulnerabilityCaseStub`).
About eight message semantics in the CM-11 join flow and the embargo Invite family.

**Touches.** CM-11 (CM-11-003, CM-11-013), CM-17, MV-10-001, VAM-04, ADR-0114 ("the
stub is its own type and its own object" part), ADR-0165,
`vultron/wire/as2/case_reference_placement.py`, the examples under
`vultron/wire/as2/vocab/examples/`, `docs/reference/messages/`.

**Open for planning.** The parse-edge rule that tells a reference-with-preview from a
full case.

---

## One Meaning for origin, and inReplyTo for Answers

Issue: #6245.

**Decision.**

- `Remove` names the collection it removes from in `origin`, everywhere.
  `Remove(Note)` and `Remove(CaseParticipant)` move from `target` to `origin`.
- `Offer(CaseParticipant)` (the CASE_MANAGER's recommendation forward, ADR-0026)
  links the recommender's `Offer(Actor)` with `inReplyTo`, not `origin`.
- `Add(VulnerabilityReport)` and `CaseProposal` drop the Vultron `offerId` for
  `inReplyTo` (the report Offer); `offerActorId` is read from that Offer or the
  report's `attributedTo`.
- A delegated emit (CM-24) keeps `attributedTo` = the asker and adds `inReplyTo` =
  the asker's request act where one exists (e.g. the owner's ownership-transfer
  proposal). The CASE_MANAGER is not modelled as anyone's `instrument`: it has its
  own authority and must be the `actor` receivers authenticate (CM-24-001).

**AS2 basis.** VOC Remove: "the actor is removing the object… [from] the origin";
Ex 28 uses origin, Ex 27 and ActivityPub use target (issues #534, #664 open; the
editor's interim advice is to read origin first). VOC `inReplyTo`: "entities for
which this object is considered a response".

**Today.** `Remove(EmbargoEvent)` alone uses `origin`
(`vultron/wire/as2/factories/embargo/lifecycle.py`); `Offer(CaseParticipant)` sets
`origin` in `vultron/core/behaviors/case/nodes/suggest_actor/emit.py`; `offerId` /
`offerActorId` in `vultron/wire/as2/vocab/activities/case/content.py`. CM-24-002's
rationale calls `attributedTo` "the AS2-standard field for recording who delegated
an action"; AS2 says only "entities to which this object is attributed".

**Touches.** CM-16-004, CP-01-007, CM-24-002, CM-24-012, the delegated-authorship
helper `vultron/core/behaviors/delegated_authorship.py`. Moving `Remove(Note)` and
`Remove(CaseParticipant)` to `origin` needs an `origin_` field on `ActivityPattern`,
so the rule "no `origin_` field" in `vultron/wire/as2/AGENTS.md` and the root
`AGENTS.md` pattern-matching row change with it; `notes/case-joining.md` shows
today's `Remove(CaseParticipant)[target=…]`.

---

## Embargo End Is an Update With a Termination Object

Issue: #6246.

**Decision.** An embargo ending is `Update(EmbargoEvent)` setting the embargo's
status to terminated, with an embedded termination object:

- a machine-read cause kind: `END_TIME_REACHED`, `THREAT_SIGNAL` (with its P/X/A
  signals; CASE_MANAGER only), `FIX_READY`, `FIX_DEPLOYED`, or `OTHER`;
- optionally the id of the act that caused it;
- the human reason in `summary`, a longer account in `content`. AS2 has no
  `description` property.

`END_TIME_REACHED` is a cause like the others, so the separate `EARLY` /
`END_TIME_REACHED` enum disappears. The CASE_MANAGER commits the change even for an
end-time termination, because EM state must change on the record.

**AS2 basis and prior art.** `Remove` would say the embargo left the case, but it
stays in the embargo register with status `terminated`. FEP-8a8e ("A common approach
to using the Event object type", draft) sends event cancellation as `Update(Event)`
with `eventStatus` (`EventCancelled`, `EventPostponed`, …, after schema.org
`eventStatus`; iCalendar `STATUS` as fallback) and has no "concluded" status or
structured cause. VOC `summary`: "a natural language summarization of the object".

**Today.** `Remove(EmbargoEvent)[origin=case]` with the reason enum in `content`
(`vultron/wire/as2/vocab/activities/embargo.py`) and the cause in the Vultron
`terminationCause` (`vultron/core/models/embargo_termination.py`,
`TerminationCauseKind`). Teardown: `vultron/core/behaviors/embargo/nodes/teardown.py`.

**Touches.** EMB-07, EMB-13-005, EMB-19, ADR-0122 (the register), the
`terminationCause` JSON-LD term, `REMOVE_EMBARGO_EVENT_FROM_CASE`.

---

## Every Vultron Property Has a JSON-LD Term

Issue: #6253. Decision record: ADR-0194. Requirements: VM-10-007 to VM-10-011,
ARCH-18-012.

**Decision.**

1. **Declared, never inferred.** Every Vultron wire field carries the property
   marker (`VULTRON_PROPERTY_EXTRA`, extended) with a one-line definition and a
   value kind. A field without it must be a term that a cited context defines: AS2,
   data-integrity v2, Multikey v1, or Controlled Identifiers v1. A test fails on a
   field that is neither. Nested models count; `exclude=True` fields do not.
2. **Typed as AS2 types its own.** IRI value → `"@type": "@id"`; a verbatim
   received document (`payloadSnapshot`) → `"@type": "@json"`; an ordered array →
   `"@container": "@list"`.
3. **One meaning per name.** Two declarations of one wire name carry the same
   definition and kind. A Vultron term never reuses an external term's name. A name
   with two meanings is renamed apart; type-scoped terms are not used.
4. **External terms from pinned copies.** The four contexts are copied byte for
   byte under `third_party/jsonld/` with a pin record (URL, SHA-256), as
   `third_party/csaf/` is. No watch job: the versioned contexts never change at
   their URLs and AS2 changes rarely and only by addition.
5. **Pending fixes are owned ratchets.** The check lands first. Each field it would
   refuse today, or that the review found duplicates an AS2 term, sits in a ratchet
   constant per owner Task (`# owner: #N`), never one shared list, and never an Idea
   as owner: `plan-issue` closes an Idea at planning, long before the field changes.
   ARCH-18-012 refuses a PR that closes an owner its ratchet still cites.

**AS2 basis.** CORE extensibility: extension terms are defined in a JSON-LD context;
the AS2 context maps unknown terms to blank nodes (`"@vocab": "_:"`). Signing is not
the risk: `eddsa-jcs-2022` signs the JSON text and expands nothing.

**Today.** `docs/ns/context.jsonld` maps the type names and four marked properties.
The generator (`vultron/metadata/wire_context/sync.py`) walks only registered
classes, so nested models are invisible, and it takes AS2 terms from field names on
this codebase's own AS2 base classes, so the unmarked `proposedEmbargo`,
`suggestedRoles` and `roles` pass as AS2. About eighty wire names have no term. The
actor profile cites Multikey v1, which does not define `assertionMethod` at top
level, so the published key is undefined to a JSON-LD reader.

**Field review.** Owners are the Tasks named in the Touches line.

| Field (class) | Finding | Becomes |
|---|---|---|
| `actorId` (`EmbargoPolicy`) | AS2 duplicate | `attributedTo` |
| `notes` (`EmbargoPolicy`) | AS2 duplicate | `content` |
| `inbox` (`EmbargoPolicy`) | AS2 name, actor-only domain | dropped |
| `caseId` (`CaseLedgerEntry`) | AS2 duplicate | `context` |
| `title` (`VulnerabilityItem`) | AS2 duplicate | `name` |
| `participantCaseName` (`CaseParticipant`) | dead; duplicates `name` | deleted |
| `caseActivity` (`VulnerabilityCase`) | dead | deleted |
| `actorParticipantIndex`, `pendingEmbargoProposalIndex` | IRI-keyed maps | off the wire |
| `assertionMethod` (actor profile) | no term in cited contexts | cite CID v1 |
| `audience`, `title`, `text`, `category` (`VulnerabilityItemNote`); `notes` (item vs case); `text` (`VulnerabilityItemId`) | name clash, AS2 clash | renamed apart |
| `state`, `status`, `kind`, `role`/`roles`/`suggestedRoles`, `caseStatus` | name clash | renamed apart |
| `offerId`, `offerActorId` | decided in § "One Meaning for origin…" | `inReplyTo` |
| stub `caseId` | decided in § "Invites Use the Spec's Slots…" | dropped |
| termination `reason` | decided in § "Embargo End Is an Update…" | `summary` |

Every other field is a Vultron term.

**Touches.** VM-10, ARCH-18, CM-05-018, CSAF-03-008, EP-01-002, EP-01-003,
EP-01-005, CLP-14-012, ADR-0194, `notes/vocabulary-registry.md` § 4a, the context
generator, `third_party/README.md`.

---

## Ledger and Status Histories Are Named Ordered Collections

Issue: #6247.

**Decision.**

1. The case ledger gets wire identity: `<case>/ledger`, an `OrderedCollection` whose
   items are the entries in order, position = `logIndex`. Identity only — no fetch
   surface; no ledger fetch surface exists today (#5089).
2. The CASE_MANAGER publishes a commit as `Add(CaseLedgerEntry,
   target=<case>/ledger)`, replacing `Announce(CaseLedgerEntry)`. A replica receiving
   it appends to its copy.
3. That `Add` is the positive acknowledgment: it carries `inReplyTo` = the committed
   act and `result` = what the act caused (a new `CaseParticipant`, follow-on
   entries). No separate ack message. A refusal stays the refusal notice.
4. Every position statement is `Read(<case>/ledger)[ledgerPosition=N]`. N = −1 means
   the sender holds nothing; the CASE_MANAGER replays everything after N. This
   replaces both `Read(<bare entry id>)` and the objectless `Reject` replay request
   (SYNC-16-027). The NAK stays `Reject(CaseLedgerEntry)`, pointing `inReplyTo` at
   the `Add`.
5. Each `CaseParticipant` gets `<participant>/statuses` and the case gets
   `<case>/statuses`, both `OrderedCollection`s (identity only). A participant asserts
   with `Add(ParticipantStatus, target=<participant>/statuses)`; the CASE_MANAGER
   records with `Add(CaseStatus, target=<case>/statuses)`. The newest item is the
   current status. Status records are never updated. ADR-0137's one message form per
   act holds.
6. Every case activity carries `context` = the case, the ledger `Add` and
   `Add(ParticipantStatus)` included.

**AS2 basis.** VOC OrderedCollection: members "are assumed to always be strictly
ordered"; pages carry `first`/`last`/`current`/`next`/`prev`/`partOf`/`startIndex`.
VOC Add: "the actor has added the object to the target". Announce is "calling the
target's attention to the object" (issues #179, #196). Primer: `result` is for
"changes of state or indirect outcomes"; VOC Ex 148 is an `Accept` whose `result`
lists the activities it caused.

**Today.** `vultron/adapters/driven/sync_activity_adapter.py` sends
`Announce(CaseLedgerEntry)`, which carries no `context` (the case is in
`object.caseId`). `vultron/wire/as2/ledger_reject_envelope.py` admits the objectless
`Reject`. The `Read` pattern accepts a bare entry id only for the position statement
(`vultron/wire/as2/extractor/_pattern.py`). `Add(ParticipantStatus)` names its case
only through the nested status's `context`. Delivery receipts are an open question
(`docs/topics/future_work/_oq-delivery-receipts.md`).

**Touches.** SYNC-16, SYNC-17 (its "not a request" wording changes: a position at −1
or behind triggers replay), SYNC-18, MSM-05, CLP-10, ADR-0107, ADR-0124, ADR-0137,
`ANNOUNCE_CASE_LEDGER_ENTRY`, `READ_CASE_LEDGER_ENTRY`, `REJECT_CASE_LEDGER_ENTRY`,
`ADD_CASE_STATUS_TO_CASE`, `ADD_PARTICIPANT_STATUS_TO_PARTICIPANT`. The guidance
notes that name `Announce(CaseLedgerEntry)` as the replication channel change with
it: `notes/case-communication-model.md`, `notes/sync-ledger-replication.md` (whose
rule "keep `Announce(CaseLedgerEntry)` ids freshly minted; never derive them" bears
on the open question below), `notes/case-actor-cluster.md`,
`notes/ownership-transfer.md`.

**Open for planning.** `result` on the ledger `Add` can list follow-on entries only if
their ids are derived ahead of time (as stub and ownership-offer ids already are), or
if the `Add` waits until they commit. Pick one.

---

## Refusal Is Its Own Type

Issue: #6254.

**Decision.** A refusal notice is `"type": ["Refuse", "Reject"]`: `class
Refuse(Reject)` in the wire vocabulary, and `vultron:Refuse rdfs:subClassOf
as:Reject` in the Vultron context. Patterns match `Refuse` before any `Reject`.
The wire then follows CLP-02-016's *refused* versus *rejected*.

**AS2 basis.** No AS2 verb fits "I won't admit your act": `Ignore` is ignoring and is
our RM defer, `Block` targets an actor and is not delivered to it (ActivityPub), `Flag`
reports content to a moderator, `TentativeReject` is not final and is our RM invalid,
`Dislike` is sentiment. CORE extension guidance: an extension type that overlaps a
core type MUST carry the core type too (the spec's example is `["Resign","Leave"]`).

**Today.** `Reject` carries 12 semantics; the refusal notice is `Reject(<refused
activity inline>)` with `inReplyTo` and `summary` (ADR-0141). A refusal of an
`Invite` or `Offer` has the decline's shape and is read by the decline use case;
`Reject(Leave(Case))` falls into `REFUSAL_NOTICE` only because no decline pattern
matches it.

**Touches.** ADR-0141, MSM-05-001, CLP-02-016, `REFUSAL_NOTICE`, the parse layer
(`type` as a list; today it is always a string).

---

## Descriptive Properties: instrument, generator, tag

Issue: #6248.

**Decision.** These are descriptive: core may index them but never routes, gates or
decides on them.

- `instrument`: optional on any act, naming the artifact a decision used (an SSVC
  decision, an embargo policy, a CSAF document). Disclosure is the sender's choice.
  Later, deliberately and one act at a time, give a specific act a defined shape
  (SSVC on RM `Join`/`Ignore` first).
- `generator`: the protocol MAY carry it; the reference implementation SHOULD build
  it as a configurable on/off feature naming the implementation (and optionally its
  version). It defaults to off (confirmed by the user), because a version in every
  message tells every participant which known vulnerabilities a deployment has.
- `tag`: an object refers *by reference* to a `VulnerabilityItem`, a weakness class
  (a Link to the CWE entry), or a participant (`Mention`, e.g. "V2, please look at this
  note"). A tag never changes recipients or entitlement (CM-10-004).

**AS2 basis.** VOC `instrument`: "one or more objects used (or to be used) in the
completion of an Activity" (one example, Listen via a Service). VOC `generator`: "the
entity (e.g. an application) that generated the object". VOC `tag` (errata):
"attachment… implies association by inclusion, while [tag] implies association by
reference"; a `Mention` in `tag` is "a mention without an associated notification".

**Today.** All three are declared on `as_Object` / the activity base and never set.
Call-outs have no wire form (`notes/call-out-configuration.md`).

**Touches.** #5132 / ADR-0187 as proposed in PR #6262 (the case's own
`VulnerabilityItem` list is the inclusion side; `tag` is the reference side — plan
them together); the JSON-LD term rule.

---

## CaseReference Holds a Link

Issue: #6249.

**Decision.** `CaseReference` stays an `as:Object`, with its own id and the
lifecycle proposed in PR #6262 (ADR-0187, CM-34): offered, admitted or declined,
ledgered. Its `url` holds an `as:Link`:

- `href` is the referenced resource; `name` and `mediaType` describe it;
- the CVE reference tags (`patch`, `vendor-advisory`, …) become the Link's `rel`
  values. Unregistered relation types are URIs, e.g. under
  `https://certcc.github.io/Vultron/ns/rel/`. The Vultron `tags` field goes away.
- The vocabulary check moves from `tags` to `rel`.

This replaces an earlier choice to make `CaseReference` a Link subtype: `as:Link` is
disjoint with `as:Object` in the AS2 ontology, and a Link is a hint about another
resource, not a resource with its own id and lifecycle.

**AS2 basis.** VOC `url`: "links to representations of the object", range
`xsd:anyURI | Link`. VOC `rel`: "The value MUST conform to both the [HTML5] and
[RFC5988] 'link relation' definitions"; not functional. RFC 8288: extension relation
types are URIs. CORE §4.2: Link properties are hints about the referenced resource.

**Today.** Built. `vultron/core/models/case_reference.py` holds `CaseReference`
(`url`, `name`) and the `CaseReferenceLink` in its `url` (`href`, `name`,
`mediaType`, `rel`); `CVE_REFERENCE_TAG_RELS` maps each CVE tag to its relation
type, and only `related` is IANA-registered, so it stays a bare name. The wire
`as_Link.rel` takes one value or a list, because `rel` is not functional.

**Touches.** CM-05-004, CM-05-005, CM-05-010, CM-05-012, CM-34-003, CSAF-03-009, and
a future FIRST VRDX-SIG vxref Idea (`FIRSTdotorg/vrdx-sig-vxref-wip`), which may
supply more `rel` values. A new value joins `CVE_REFERENCE_TAG_RELS` (or the
vocabulary beside it) and the `docs/ns/` relation table together.

---

## Update Versus a New Object

Issue: #6250.

**Decision.** Identity decides (the rule is in
[activitystreams-semantics.md](activitystreams-semantics.md)). Give these an
`Update` form with a received use case:

- `Update(Note)` by its author;
- `Update(VulnerabilityReport)` by its Reporter;
- `Update(CaseParticipant)` by that participant, for its own details.

`Remove(Note, origin=<case>)` takes a note out of a case.

A `VulnerabilityItem` is case content, not one participant's own object, so a
participant changes it by offering the `Update` to the CASE_MANAGER
(`Offer(Update(VulnerabilityItem))[target=case]`, CM-34-002 and ADR-0187 as
proposed in PR #6262), the pattern of § "Approvals Are Offers of the Act".

**`Update` is partial.** ADR-0187, proposed in PR #6262, makes an `Update` replace
the fields it carries and leave the rest. Every `Update` in this note follows that
meaning, including the merge freeze and the embargo end. AS2 itself leaves
`Update`'s scope open (ActivityPub makes client-to-server `Update` partial and
server-to-server a full replacement), so the meaning is Vultron's rule, not AS2's.

**Today.** `Update` is sent only by the CASE_MANAGER (case owner, participant records,
consent rows) and nothing receives it. `REMOVE_NOTE_FROM_CASE` has a received use case
but no factory or trigger; only a demo sends it.

**Open for planning.** A revised report is an authored statement others may have
relied on; decide whether a report revision is an `Update` or a new report. Signing:
an `Update` replaces content someone signed earlier.

---

## Approvals Are Offers of the Act

Issue: #6251 (poll Idea: #6258).

**Decision.** A yes/no approval of a concrete act is `Offer(<the act>)`, answered with
`Accept` or `Reject`. The status-adoption approval (RSH-07-004, today a gate that fails
closed with no wire form) becomes the CASE_MANAGER sending the Owner
`Offer(Add(CaseStatus, target=<case>/statuses))`. `Question` is for choices and open
inquiries where no single act is proposed.

The ownership transfer's `Offer(Offer(VulnerabilityCase))` (ADR-0148) is this pattern
and stays, plus the `inReplyTo` above.

**AS2 basis.** VOC Offer can propose an action ("Sally is offering to add a File to
Folder A"); `Question` is intransitive, with `oneOf`/`anyOf`, answers as separate
objects with `inReplyTo`, the outcome in `result`, and `closed`.

Item and reference offers, as PR #6262 proposes them (CM-34-001 to CM-34-004,
ADR-0187), follow this pattern.

**Touches.** RSH-07-004, `RequireCaseOwnerApprovalNode`, #2885 (the same gap from the
ask side), ADR-0148, CM-34 (proposed in PR #6262).

**Open for planning (separate Idea).** A `Question` poll "what is the latest end date
you would accept?", after which the CASE_MANAGER proposes the earliest answer
(shortest-wins). It must reconcile with ADR-0100, which retired the multi-candidate
embargo poll (`ChoosePreferredEmbargo`) and did not defer it; the difference is that
this poll collects each participant's bound instead of choosing among candidates.

---

## TentativeAccept and Withdrawal by Undo

Issue: #6252.

**Decision.**

- `TentativeAccept(Invite(EmbargoEvent))` is admitted as a ledgered, purely
  informational signal ("we expect to agree, pending legal review"). It is not
  consent, gives no coverage, and does not change the CM-28 RSVP lapse.
- The author of an unanswered `Offer` or `Invite` may withdraw it with
  `Undo(<that Offer or Invite>)`; an answered one cannot be withdrawn. This adds
  withdrawal of a report `Offer`, a case `Invite`, and a role `Offer`, in the shape the
  two existing withdrawals use (`UNDO_CASE_OWNERSHIP_TRANSFER`,
  `UNDO_INVITE_TO_EMBARGO_ON_CASE`).

**AS2 basis.** VOC TentativeAccept: "A specialization of Accept indicating that the
acceptance is tentative" (Ex 11). VOC Undo's example retracts an Offer; ActivityPub
requires the same actor.

**Open for planning.** The report withdrawal cut-off: a Reporter that sent one report
to several recipients (CBT-06) may withdraw from one after it was read (RV) but before
it was answered; decide whether *read* or *answered* is the cut-off. A tentative answer
extending the RSVP deadline is a separate Idea.

---

## Create(CaseParticipant) Names Its Case in context

Issue: #6295 (from Concern #6260).

**Decision.** The CASE_MANAGER's `Create(CaseParticipant)` ledger entry drops `target`
and keeps `context` = the case. It stays a `Create`: the act is "this record now
exists", and seating is not part of it. Only the CASE_MANAGER sends it, so a receiver
needs no rule for a stray `target`.

`Add(CaseParticipant, target=<case>)` was considered and rejected for now: that shape
is already the Case Owner's reinstatement request (CM-31-011), and a pattern cannot
tell the two apart by sender. Idea #6293 would move the Owner's requests to name the
Actor, which frees `Add(CaseParticipant)`.

**AS2 basis.** CORE App. B: the AS1 "post" verb maps to `Create` without a target and
to `Add` with one.

**Today.** `create_participant_activity` sets `target=case_target_ref(target)`
(`vultron/wire/as2/factories/case_participant.py`); `_CreateParticipantActivity`
declares `target`. Both callers already set `context`. The pattern and the replica's
apply read no `target`: the apply takes the case from the ledger entry's `case_id`.

**Touches.** The factory and wire class, `record_case_participant_created`, the
`create_participant` example, the generated "Create case participant" message page.

---

## Deferred Ideas

Each is its own Idea; none is designed here. The three wire defects the review found
are Concerns #6259, #6260 and #6261.

- **Owner's requests name the Actor** (#6293). Removal and reinstatement name the
  Actor, not the `CaseParticipant`; the CASE_MANAGER applies them to that actor's one
  record (CM-19) and keeps it, so a reinstated participant keeps history and consent
  (ADR-0116). Needs an ADR revising ADR-0116's choice of message.
- **Fetchable ledger** (#5089). `GET <case>/ledger` paged by `OrderedCollectionPage` and
  `startIndex`. `Read(<case>/ledger)[ledgerPosition=N]` is then the push form of
  `GET …?startIndex=N+1`. Adds the first ledger fetch surface; needs authorization
  design.
- **CASE_MANAGER relocation** (#6255). If a case's ledger ever moves to another host,
  the sentence is `Move(Case, origin=<old manager>, target=<new manager>)`. Touches
  ledger continuity, hash chains, and every replica's recipient.
- **Flag and case moderation** (#6256). `Flag(object)` for conduct or content concerns
  ("V9 broke the embargo", "this note leaks exploit detail", abuse). Out of scope for
  the current implementation. Open: is an accusation visible to the accused
  (ledgered) or private to the CASE_MANAGER and Owner. P/X/A statuses cover the
  observable facts meanwhile. AS2 issue #609 moved to the SWICG Trust & Safety task
  force.
- **TLP and public followers** (#5133). `audience` for TLP markings — but TLP restricts
  onward sharing while `audience` names relevance, so weigh `audience` against a TLP
  marking object in `tag`. `Follow` fits only non-participants after public
  disclosure.
- **`preview` beyond the stub** (#6257). A report previewed to a prospective
  recipient, a reserved vul record, a draft advisory, what non-signatories may see
  of a gated object. A preview may mark a withheld field `Redacted`, and
  only a preview may (`notes/selective-disclosure.md`, ADR-0193).

## Sources

Where the cited specifications live, so a planner can check a quotation:

- **AS2 Vocabulary** (`VOC`): <https://www.w3.org/TR/activitystreams-vocabulary/>.
  **AS2 Core** (`CORE`): <https://www.w3.org/TR/activitystreams-core/>.
- **AS2 source, errata and issues**: <https://github.com/w3c/activitystreams>
  (`ERRATA.md`, `activitystreams2.owl`, `ns/activitystreams.jsonld`; issue numbers
  such as #534, #609, #619 are in that repository). The JSON-LD context is served at
  <https://www.w3.org/ns/activitystreams>.
- **Primer**: <https://www.w3.org/wiki/Activity_Streams/Primer>.
- **ActivityPub** (cited only for Update, Delete, Add, Remove, Undo):
  <https://www.w3.org/TR/activitypub/>.
- **FEP-8a8e** (event status): <https://codeberg.org/fediverse/fep>, file
  `fep/8a8e/fep-8a8e.md`. **schema.org `eventStatus`**:
  <https://schema.org/eventStatus>.
- **RFC 8288** (link relations, extension relation URIs):
  <https://www.rfc-editor.org/rfc/rfc8288>.
- **CSAF 2.1**: <https://github.com/oasis-tcs/csaf>. **CVE record schema** (reference
  tags): <https://github.com/CVEProject/cve-schema>. **FIRST VRDX-SIG vxref**:
  <https://github.com/FIRSTdotorg/vrdx-sig-vxref-wip>.

## Closed With No Change

- `endTime` is the end of its own subject: an RSVP time on an `Offer`, `Invite` or
  `Question`, the end on an `EmbargoEvent`. Conforms (VOC: "the moment the activity
  concluded or is expected to conclude").
- `context` = the case stays. `cc`, `bto`, `bcc`, `duration`, `location`, `Block`,
  `Delete`/`Tombstone`, `Like`: no CVD sentence needs them. `Block` is local inbox
  policy; nothing in an append-only case is deleted.
