---
status: accepted-provisional
date: 2026-11-18
created: 2026-11-18
updated: 2026-11-18
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0122, ADR-0130, ADR-0180, ADR-0202, ADR-0203 (the records
  this one consolidates); ADR-0113, ADR-0116, ADR-0124, ADR-0175, ADR-0199,
  ADR-0201; specs/case-management.yaml CM-10, CM-18, CM-31;
  specs/message-semantics-mapping.yaml MSM-07; specs/embargo-policy.yaml EP-05,
  EP-08, EP-09; specs/em-behavior.yaml EMB-13, EMB-16, EMB-17, EMB-18, EMB-19;
  issues #6481, #6482, #6483, #6510, #6625, #6421
informed: []
supersedes:
  - 0122-per-embargo-participant-consent.md
  - 0130-em-is-computed-from-the-embargo-register-under-the-em-transition-table.md
  - 0180-the-case-owner-adds-an-embargo-to-the-case-and-answers-a-proposal-by-pointing-at-it.md
  - 0202-an-embargo-stores-its-own-status-and-the-register-is-the-cases-ordered-list-of-embargoes.md
  - 0203-an-embargos-end-is-an-update-of-the-embargo-announced-to-every-signatory.md
partially_supersedes:
  - 0048-pec-no-embargo-is-absence-not-pre-consent.md
  - 0091-rename-pec-no-embargo-to-unbound.md
  - 0093-signatory-declined-pec-transition.md
  - 0116-removing-a-participant-withdraws-entitlement-not-membership.md
  - 0118-pec-expired-and-unbound-exited-states.md
stakeholder_type: [project-contributor]
---

# How Embargo Status and Participant Consent Are Recorded

## Context and Problem Statement

A case can have several embargoes over its life: proposals, the one in force, revisions that replace it, and ones that were rejected, cancelled or ended.
Each participant answers each of them, and the case's embargo management (EM) state follows from all of them.

Five records decided how that is held and sent.
ADR-0122 replaced a scalar consent state and an accepted-embargo list, which disagreed, with an embargo register on the case and one consent row per participant and embargo, and derived EM from the register.
ADR-0130 kept the EM transition table as a rule every register change obeys, and set the moves when several proposals are open.
ADR-0180 made the Case Owner's activation an `Add` naming the proposal it answers, and refused an activation from an owner that had declined.
ADR-0202 moved each embargo's status, revision link and termination onto the embargo itself.
ADR-0203 made an embargo's end an `Update` of the embargo, announced to every signatory.
ADR-0122 alone reached revision 7 by edits in place, and each later record replaced part of the ones before it, while ADR-0199 changed the owner's decision messages again.
The rule as it stands could be read only by laying the five, and part of ADR-0199, over each other.

This record states those decisions as one.
It decides nothing they did not.
Its storage and message shapes are the ones #6481, #6482, #6483 and #6625 build; until they land, the code still holds a register entry beside each embargo and still sends `Add`, `Reject(EmbargoEvent)` and `Remove` for the owner's decisions and the end.

What records hold a case's embargoes and each participant's consent to them, so that every state is named and stored once, and which messages change them?

## Decision Drivers

- **One fact, recorded once.** Two records of the same fact can disagree, and did (Concern #3884).
- **Every fact about an object is on that object**, so a message about the object can state the change.
- **Every state a machine can be in is named and written**; no state is inferred from a missing record.
- **The case keeps everything that happened to it**, including every embargo proposed on it.
- **The EM state machine stays the protocol's model**: it must not be broken by how its state is stored, and a defect underneath must surface as a refused change.
- **The content gate must keep answering "is this participant bound by the embargo in force?" exactly** (CM-10-004).
- **Agreeing to N days is agreeing to every shorter period** (EP-05).
- **Each message means one thing, whoever sends it**, and its verb says what was done; no handler reads the sender to learn what a message means.
- **An actor sends the decision it has the authority to make as the act itself**, and the CASE_MANAGER admits or refuses it (ADR-0199).
- **The case is rebuildable from its ledger** (ADR-0124): every change is caused by a committed protocol message, and replicas copy entries, never work changes out.
- **Pre-1.0 there is one protocol and one storage version**, so a replaced shape is removed, not kept beside its successor (ADR-0175).

## Considered Options

1. **Embargoes carry their own status in an ordered register on the case; every consent row is written; EM is computed from the register under the EM transition table; every change of an embargo's status is an `Update` of the embargo.**
2. **Keep the hybrid**: a scalar consent state plus a list of accepted embargoes, with reconciliation rules.
3. **Make the accepted-embargo list authoritative** and drop the scalar.
4. **Consent rows with "not asked" as a missing row, and EM as its own machine** (ADR-0122 revision 1).
5. **The derivation table as EM's only rule**, with no EM transition table.
6. **The register keeps each embargo's status beside it**, or the register entry becomes an addressable object of its own.
7. **The owner decides by `Accept`, `Add` or `Reject` of the embargo with the case as `target`**, and an embargo ends by `Remove(EmbargoEvent)` with its reason in `content`.

## Decision Outcome

Chosen option: **option 1**, because it is the only option in which every state is named and stored once, EM, "signatory" and "lapsed" are reads that cannot disagree with what they read, and every message about an embargo is true of its sender.

### Decision details

1. **The case's embargo register is its ordered list of embargoes.**
   Every embargo ever proposed on the case is appended to it and never removed (ADR-0202).
   Each embargo stores, beyond its terms, its `status`, the embargo an activated revision `replaces`, and, once terminated, its termination (detail 7).
   A copy of the case carries the list, each embargo in a form an object slot allows.

   | Status | Meaning |
   |---|---|
   | `PROPOSED` | An open proposal, awaiting the Case Owner's decision. |
   | `ACTIVE` | In force. |
   | `REJECTED` | The Case Owner declined the proposal. |
   | `SUPERSEDED` | Was in force; a revision replaced it. |
   | `CANCELLED` | Closed with no owner decision, because the embargo question became moot. |
   | `TERMINATED` | Was in force when the case's embargo ended. |

   | Register step | Change |
   |---|---|
   | `PROPOSE` | a new embargo, `PROPOSED` |
   | `ACTIVATE` | `PROPOSED → ACTIVE` |
   | `REJECT` | `PROPOSED → REJECTED` |
   | `SUPERSEDE` | `ACTIVE → SUPERSEDED`, in the same step as another embargo's `ACTIVATE` |
   | `TERMINATE` | `ACTIVE → TERMINATED`, recording the termination |
   | `CANCEL` | `PROPOSED → CANCELLED`, in the same step as a `TERMINATE`, or on a threat signal while no embargo is `ACTIVE` (EMB-16-001) |

   `REJECTED`, `SUPERSEDED`, `CANCELLED` and `TERMINATED` are final.
   Every step keeps four invariants, and a step that would break one is refused:
   1. At most one embargo is `ACTIVE` and at most one is `TERMINATED`, and never one of each.
   2. A `SUPERSEDED` embargo exists only alongside exactly one `ACTIVE` or `TERMINATED` one.
   3. No embargo is `PROPOSED` while one is `TERMINATED`.
   4. Once a step has left an embargo `TERMINATED`, no later step adds or changes one.

   A step is the whole change one act causes, so a `TERMINATE` and the `CANCEL` of every open proposal are one step, checked together (EP-08-004).
   An open proposal leaves `PROPOSED` only by the owner's activation or rejection, or by `CANCEL` when the question becomes moot; an RSVP deadline never closes it.
   Activating one proposal leaves every other one open, now as a revision of the embargo in force, so the answers already given to it stay valid.
   Prose qualifies the shared words: "`EM.ACTIVE`" for the case, "status `ACTIVE`" for one embargo.

2. **EM is computed from the register, under the EM transition table.**
   EM is never set directly.

   | `ACTIVE` | `PROPOSED` | `TERMINATED` | EM |
   |---|---|---|---|
   | 0 | 0 | 0 | `NONE` |
   | 0 | ≥1 | 0 | `PROPOSED` |
   | 1 | 0 | 0 | `ACTIVE` |
   | 1 | ≥1 | 0 | `REVISE` |
   | 0 | 0 | 1 | `EXITED` |

   Every register step maps to one EM trigger — `PROPOSE` to `propose`, `ACTIVATE` to `accept`, `REJECT` and a threat-signal `CANCEL` to `reject`, `TERMINATE` to `terminate` — and the EM move it causes must be one of the table's moves for that trigger (EMB-18-005).
   A step whose EM move is not in the table is refused with no write, in the same place a broken invariant is, so the CASE_MANAGER and every replica apply the check alike (EMB-18-013).

   | Trigger | Source → Destination |
   |---|---|
   | `propose` | `NONE → PROPOSED`, `PROPOSED → PROPOSED`, `ACTIVE → REVISE`, `REVISE → REVISE` |
   | `reject` | `PROPOSED → NONE`, `PROPOSED → PROPOSED`, `REVISE → ACTIVE`, `REVISE → REVISE` |
   | `accept` | `PROPOSED → ACTIVE`, `PROPOSED → REVISE`, `REVISE → ACTIVE`, `REVISE → REVISE` |
   | `terminate` | `ACTIVE → EXITED`, `REVISE → EXITED` |

   EM leaves `PROPOSED` or `REVISE` only when the last open proposal is off the table, and a case that has had an embargo in force never returns to `NONE` or `PROPOSED`.
   `CaseStatus` keeps an EM field as a copy the case stamps from the register; a received status may report EM but never move it, and one that asserts a different EM is refused (RSH-09-005).

3. **Every participant holds one consent row per embargo, and every row is written.**
   A participant record holds one `EmbargoConsent` row for each embargo in the register (CM-18-001).
   When an embargo is proposed, every current participant gets an `UNINVITED` row for it; when a participant record is created, it gets an `UNINVITED` row for every embargo already in the register (CM-18-019, CM-18-020).
   A missing row is a defect, and reading one raises (CM-18-021).
   A row carries its invitation's RSVP deadline only while `INVITED`, so a participant can hold concurrent invitations with their own deadlines.

   | State | Meaning |
   |---|---|
   | `UNINVITED` | Not asked about this embargo. The start state. |
   | `INVITED` | Asked; no answer yet. |
   | `AGREED` | Agreed: explicitly, as its proposer, by seeding, or by carry-over. |
   | `DECLINED` | Refused it, or withdrew from it. |
   | `TIMED_OUT` | Invited, and the RSVP deadline passed with no answer. Not a refusal. |

   | Trigger | From | To |
   |---|---|---|
   | `INVITE` | `UNINVITED`, `DECLINED`, `TIMED_OUT` | `INVITED` |
   | `AGREE` | `UNINVITED`, `INVITED`, `DECLINED`, `TIMED_OUT` | `AGREED` |
   | `DECLINE` | `UNINVITED`, `INVITED`, `AGREED`, `TIMED_OUT` | `DECLINED` |
   | `TIME_OUT` | `INVITED` | `TIMED_OUT` |
   | `CARRY_OVER` | every state except `AGREED` | `AGREED` |

   Asking again does not undo an answer, so `AGREED` refuses `INVITE` (CM-18-004).
   `AGREE` from `DECLINED` is the participant changing its own answer; seeding and joining are not answers it gave, and leave a declined row declined.
   `CARRY_OVER` is caused only by activating a revision that ends no later than the embargo it replaces, for each participant whose row for the replaced embargo is `AGREED`, a declined row on the revision included (EP-05-003); activating a longer revision carries no one over (EP-05-001).
   A deadline passing times out only that invitation's row (CM-18-002).
   A row for an embargo in a final status accepts no trigger; a late answer to terms no longer current is answered with an invitation to the current embargo (EMB-17).
   A late joiner stays `UNINVITED` on embargoes no longer in force, and is invited only to the one in force and to open revisions.

4. **Signatory and lapsed are reads, not states.**
   A participant is a **signatory** when its row for the `ACTIVE` embargo is `AGREED`; the content gate reads it (CM-10-004).
   A participant has **lapsed** when an embargo is `ACTIVE`, its row for it is neither `AGREED` nor `DECLINED`, and, following `replaces` back from it, the first embargo whose row is `AGREED` or `DECLINED` has an `AGREED` row: it was bound, and the embargo in force has since become something it did not agree to.
   No consent row records a lapse or an exit (CM-18-016), and after termination nobody is a signatory and nobody has lapsed.

5. **Participants answer invitations; the Case Owner decides for the case by updating the embargo.**
   - `Invite(EmbargoEvent)` proposes a new embargo, `PROPOSE`, with the proposer's row `AGREE` and each invitee's `INVITE`; it relays through the CASE_MANAGER (ADR-0113).
     An `Invite` for an embargo already in the register re-invites, invites a late joiner, or makes the fresh invitation of EMB-17, and moves only the invitee's row.
   - `Accept(Invite(EmbargoEvent))` and `Reject(Invite(EmbargoEvent))` are always the sender's own consent, the Case Owner's included: `AGREE` or `DECLINE` on the sender's row, and no register change (MSM-07-003, MSM-07-004, MSM-07-011).
     A `Reject` from an `AGREED` row on the embargo in force is refused, because leaving an embargo one is bound by is withdrawal (MSM-07-014).
   - `Leave(EmbargoEvent)` naming the embargo in force is withdrawal: `DECLINE` on the sender's `AGREED` row for it, and on each open proposal's row it had agreed to (MSM-07-010, MSM-07-034).
     It needs no Invite, so it serves a reporter or joiner who became a signatory without answering one, and it is refused from the Case Owner, who ends an embargo instead (MSM-07-036).
   - The Case Owner puts a proposal in force with its own `Update(EmbargoEvent)` setting `status` active, and rejects one with its own `Update(EmbargoEvent)` setting `status` rejected; each names the proposal's `Invite(EmbargoEvent)` in `inReplyTo` (ADR-0199).
     The CASE_MANAGER admits either only from the Case Owner and only for an open proposal, and refuses activation while the case is public, exploited or attacked (EMB-02-002).
     An `Update` of an embargo changes its status, and its termination when it ends; its terms change only through a revision proposal.
   - Activation is `ACTIVATE` with `SUPERSEDE` of any embargo in force, and `CARRY_OVER` as detail 3 says.
     It records the owner's `AGREE` when the owner's row holds no answer it gave (`UNINVITED`, `INVITED` or `TIMED_OUT`), leaves an `AGREED` row as it is, and is refused when the owner's row is `DECLINED`: the owner accepts the invitation first, so the ledger records each answer as it was given (MSM-07-037).
   - Rejection is `REJECT` and changes no consent row (MSM-07-031); the owner's own answer does not constrain it.
   - Case initialization seeds the Case Owner's and the reporter's `AGREE` on the default embargo, and the `Accept` of the full-case Invite seeds the joiner's (CM-14-003, CM-14-005, ADR-0121).
   - An invitation's RSVP deadline passing is committed as an entry and is `TIME_OUT` on that row (CM-28-009).

6. **A threat signal ends the embargo, or abandons the proposals.**
   A committed case status that sets P, X or A, with an embargo in force, terminates it with a `THREAT_SIGNAL` cause and cancels every open proposal; with none in force, it cancels every open proposal (EMB-16-001).

7. **An embargo's end is an `Update` of the embargo, with its termination.**
   An embargo ends with `Update(EmbargoEvent)` setting `status` to terminated and recording its termination: its cause, the act that caused it when known, and a human-readable reason in `summary` that the protocol does not read (ADR-0203).
   A cause is an object discriminated on `kind`, each kind with its own details, so a new cause is a new kind: end time reached; `THREAT_SIGNAL`, with the signals that ended it; `FIX_READY`, with the vendors whose readiness made the quorum; `FIX_DEPLOYED`; and `OTHER`.
   End time reached is a cause like the others, so no separate end-time-or-early value is carried (#6421).
   The CASE_MANAGER ledgers every such `Update`.
   It sends its own when it ends an embargo at its end time or on a threat signal; only the CASE_MANAGER names `THREAT_SIGNAL`, read from the case's own P/X/A state.
   The Case Owner's early end is the Owner's own `Update`, sent to the CASE_MANAGER, which records the Owner's cause as the Owner's claim and admits the `Update` as the ledger entry, or refuses it with a refusal notice, as it does a `THREAT_SIGNAL` cause from the Owner.
   An embargo reaches its end time through either of two requests, the CASE_MANAGER's lazy check or an outside request such as a Sentinel, which share one idempotent path: one that arrives after the end commits nothing and is answered as already done (EMB-13-003, EMB-13-006, EMB-13-007).
   An end-time termination claimed before the end time is refused, by the CASE_MANAGER and by a replica that replays it (EMB-13-008).
   The end runs the full step: `TERMINATED` with its termination, every open proposal `CANCELLED`, EM `EXITED`.
   A replica records the termination the entry carries and never works a cause out from its own state (EMB-13-016, EMB-13-017).

8. **Every participant an embargo may have bound is told it ended, by an `Announce` of the act.**
   After the end commits, the CASE_MANAGER sends `Announce(<the Update>)` to every active participant and to every signatory the ledger fan-out does not reach, such as a removed participant, on every termination, the end time included.
   The announced act carries the embargo and its termination and no other case content (CM-31-031).
   A signatory whose stream is paused applies the end from the notice, and a later replay of the entry carrying the same act changes nothing.
   The notice of a shorter revision follows the same rule: it announces the act that made the revision active.

9. **Each change is a ledger entry, and one apply function copies every entry.**
   A ledger entry records one AS2 activity with its object.
   An act that changes the register is one entry, and applying it performs the whole register step; no separate entry records a supersede or a cancel.
   Each consent row the CASE_MANAGER creates or changes as a consequence of an act is its own CASE_MANAGER entry after the act's entry: `Create(EmbargoConsent)` for a new row, `Update(EmbargoConsent)` for a changed one (MSM-07-023).
   Where the act is the participant's own answer, its entry is the row's entry, and no second one records it.
   A consent row is an AS2 object carried in full: `type` `EmbargoConsent`, an `id` derived from the participant actor and the embargo so no node mints one, `attributedTo` the participant actor, `embargoId`, `state`, and `rsvpDeadline` on an `INVITED` row only; it is built with no `published` or `updated` time, so building or copying one reads no clock.
   The CASE_MANAGER and every replica apply each entry through the same function (ADR-0124): it checks the starting state the entry implies — a legal register step, a new row starting `UNINVITED` or one transition from it, a held row reaching the carried state by one transition, no change for an embargo in a final status — mints no id, reads no clock or store, and never writes EM.
   An entry that does not start where the case is, is refused: on the CASE_MANAGER the trial apply stops the act before anything is committed, and on a replica the entry is held for gap handling, never patched over.

10. **A former consent key is an unknown key.**
    The scalar consent state, the computed adherence field and the accepted-embargo list are gone, and their former wire keys are set aside and reported like any other unknown key (ADR-0175).
    The stored shape changes with no migration.

### Consequences

- Good, because every state is named and stored once: no machine starts from an absent record, nothing that is only a read is drawn as a state, and every fact about an embargo is on the embargo.
- Good, because consent, the register and EM each have one record or one derivation, so "bound", "lapsed" and EM cannot disagree with what they read.
- Good, because the EM state machine is enforced on every change, on the CASE_MANAGER and every replica alike, and tools that draw it read the table instead of encoding their own copy.
- Good, because the case keeps its whole embargo history, including rejected and cancelled proposals and the consent given to them.
- Good, because each message has one meaning: a participant's answer, a withdrawal and the owner's decision for the case are different messages, and every change of an embargo's status is an `Update` of the embargo.
- Good, because a leftover proposal keeps the consent given to it, and a late answer can still be honoured.
- Good, because one notice reaches everyone an embargo may have bound, and carries the act that ended it.
- Bad, because rows grow to participants × embargoes per case and are never pruned; at the expected scale this is small.
- Bad, because a leftover proposal nobody pursues keeps the case in `REVISE` until the owner rejects it.
- Bad, because the owner's activation, rejection and early end share the shape `Update(EmbargoEvent)`, so the patterns that tell them apart read the `status` the `Update` sets.
- Bad, because an owner that declined and then changes its mind sends two activities, its `Accept` and its activation.
- Bad, because the derivation, the EM table and the register's own steps are three related tables to keep consistent; the every-change check makes a mismatch fail loudly.
- Bad, because the wire format and the stored case change, with no compatibility kept before 1.0.

## Validation

- `test/core/states/test_participant_embargo_consent.py` drives the consent row machine through every legal trigger and refuses every illegal one.
- `test/core/states/test_embargo_register.py` and `test/core/models/test_embargo_register.py` hold the register steps and invariants.
- `test/core/states/test_em_transition_table.py` holds the EM transition table and the check every register step makes against it.
- `test/core/models/test_embargo_termination.py` covers the termination and its cause.
- `test/demo/test_rebuild_from_ledger.py` rebuilds a case, its register and its consent rows from the ledger.
- The issues that build details 1, 5, 7 and 8 (#6481, #6625, #6482, #6483) carry their own acceptance tests.

## Pros and Cons of the Options

### Embargoes carry their status; written rows; EM computed and checked; status changes are Updates

- Good, because each answer, refusals, time-outs and never-asked included, is stated once and written.
- Good, because EM, "signatory" and "lapsed" are reads over stored records.
- Bad, because every reader of the former records, and the stored case schema, had to change.

### Keep the hybrid

- Good, because nothing changes.
- Bad, because it produced Concern #3884 and needs reconciliation rules plus a special case to stay coherent.

### List authoritative, scalar dropped

- Good, because there is one record.
- Bad, because the list records only acceptance: it cannot tell declined from timed out from never asked.

### Rows with "not asked" as a missing row, EM as its own machine

- Good, because consent has one record.
- Bad, because the start state is inferred from absence, the case cannot list its embargoes, and EM's own table can disagree with the embargoes the case holds, and did.

### The derivation table as EM's only rule

- Good, because there is one table to maintain.
- Bad, because the EM state machine survives only as a picture: nothing stops a register change from making a move the EM model forbids.

### The register keeps each embargo's status, or the entry is its own object

- Good, because storage does not change, or the record that changes has a name of its own.
- Bad, because the same facts appear twice on the wire, or a Vultron object no outside reader knows holds facts that belong to the embargo, and a message that an embargo changed has nothing on the embargo to point at.

### Owner decisions as `Accept`, `Add` or `Reject` with the case as target, and an end as `Remove`

- Good, because each decision has a shape of its own.
- Bad, because `Accept` reads as an answer and `Add` as the embargo joining a case that already holds it, so a receiver tells a case change from a consent only by the object's shape.
- Bad, because `Remove` says the embargo left the case, though it stays on it, terminated, and its reason travelled in `content`, which ActivityStreams 2.0 defines as natural-language text.

For withdrawal, `Reject(Invite(EmbargoEvent))` of the embargo in force was weighed and not chosen, because one `Reject` would mean refusal or withdrawal depending on the case's state, and a reporter or joiner holds no Invite to reject.
`Undo(Accept(...))` reads as "not answered" rather than "not bound", and a seeded or joining signatory has no `Accept` to undo.
`Reject(EmbargoEvent)` would share a shape with an owner decision.

## More Information

This record supersedes, whole:

- [ADR-0122](archived/0122-per-embargo-participant-consent.md): the register, its statuses, steps and invariants are detail 1; EM derived from the register is detail 2; the consent rows are detail 3; signatory and lapsed are detail 4; the participant messages and withdrawal are detail 5; the threat signal is detail 6; the termination cause kinds and the two end-time requests are detail 7; the ledger shapes and the apply function are detail 9; the retired keys are detail 10.
- [ADR-0130](archived/0130-em-is-computed-from-the-embargo-register-under-the-em-transition-table.md): the EM transition table and its every-change check are detail 2, and the multi-proposal rules (activation leaves the others open, a deadline never closes a proposal) are detail 1.
- [ADR-0180](archived/0180-the-case-owner-adds-an-embargo-to-the-case-and-answers-a-proposal-by-pointing-at-it.md): participants answer invitations and the owner decides for the case, each decision naming its proposal, the declined-owner refusal, and the owner's answer not constraining its rejection are detail 5.
- [ADR-0202](archived/0202-an-embargo-stores-its-own-status-and-the-register-is-the-cases-ordered-list-of-embargoes.md): the embargo's own status, revision link and termination, and the register as an ordered list, are detail 1.
- [ADR-0203](archived/0203-an-embargos-end-is-an-update-of-the-embargo-announced-to-every-signatory.md): the end as an `Update` is detail 7, and the `Announce` of it to every signatory is detail 8.

Not carried forward, because each had been overtaken before this record:

- ADR-0122's activation by `Accept(EmbargoEvent, target=VulnerabilityCase)`, ADR-0180's by `Add(EmbargoEvent, target=VulnerabilityCase)`, and rejection by `Reject(EmbargoEvent, target=VulnerabilityCase)`: ADR-0199 made both owner decisions `Update`s of the embargo.
- ADR-0122's rule that an owner that declined a proposal may still activate it: ADR-0180 refused it.
- The termination `Remove(EmbargoEvent)`, its `END_TIME_REACHED`/`EARLY` value in `content`, the `terminationCause` property and the rule that an end-time termination has no cause: ADR-0203 replaced them.
- The separate direct copy of a termination to a signatory the fan-out skips: ADR-0203's one `Announce` replaced it.
- ADR-0122's statement that the retired consent keys are refused inbound by name: ADR-0175 made them unknown keys.
- ADR-0122's retirement of the EM transition table: its own revision 5 and ADR-0130 withdrew it.
- ADR-0122's revision history and its list of effects on earlier decisions: the effects that still hold are the partial supersessions below.

It carries forward the partial supersession of five live records:

- [ADR-0048](0048-pec-no-embargo-is-absence-not-pre-consent.md): absence of an embargo is not pre-consent stands, as `UNINVITED`.
- [ADR-0091](0091-rename-pec-no-embargo-to-unbound.md): `UNBOUND` is no longer a state.
- [ADR-0093](0093-signatory-declined-pec-transition.md): `DECLINE` from a signatory stands as `DECLINE` from an `AGREED` row caused by `Leave(EmbargoEvent)`, and its "lapse at activation, never at proposal" rule stands as the lapsed read.
- [ADR-0118](0118-pec-expired-and-unbound-exited-states.md): its unbound-exited state is replaced, because termination is the register's fact; its expired state stands as `TIMED_OUT`.
- [ADR-0116](archived/0116-removing-a-participant-withdraws-entitlement-not-membership.md): its embargo-change notices to a removed participant are replaced by detail 8.

Related:

- [ADR-0113](0113-embargo-revision-negotiation-relays-through-the-case-manager.md): embargo proposals relay through the CASE_MANAGER.
- [ADR-0124](0124-case-is-a-projection-of-its-ledger.md): the case is a projection of its ledger, and replicas copy entries.
- [ADR-0175](0175-before-1-0-one-protocol-and-storage-version-so-a-former-field-name-is-an-unknown-key.md): before 1.0, a former field name is an unknown key.
- [ADR-0199](0199-an-actor-sends-the-decision-it-makes-and-offers-only-what-another-decides.md): an actor sends the decision it makes as the act, which is why the owner's decisions and early end are its own `Update`s.
- [ADR-0201](0201-an-embargoevent-is-a-vultron-extension-type-and-a-subtype-of-event.md): the embargo's wire type.
- [ADR-0056](archived/0056-embargo-adherence-computed-field.md), superseded by ADR-0122, stays retired.

Generated spec requirements: `case-management.yaml` CM-10, CM-18 and CM-31; `message-semantics-mapping.yaml` MSM-07; `embargo-policy.yaml` EP-05, EP-08 and EP-09; `em-behavior.yaml` EMB-13, EMB-16, EMB-17, EMB-18 and EMB-19.
