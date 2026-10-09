---
status: proposed
date: 2026-10-06
created: 2026-10-06
updated: 2026-10-07
revision: 2
deciders: Allen D. Householder
consulted: >-
  Claude Sonnet 5.5; Claude Opus 5.5; Issue #4178, Concern #4284, Concern #3884,
  Issue #4153, PR #4002, PR #4267; ADR-0048, ADR-0056, ADR-0091, ADR-0093,
  ADR-0113, ADR-0118, ADR-0124; specs/case-management.yaml CM-10, CM-18;
  specs/message-semantics-mapping.yaml MSM-07; specs/embargo-policy.yaml EP-05,
  EP-08, EP-09; specs/em-behavior.yaml EMB-11, EMB-16, EMB-17
informed: []
supersedes: 0056-embargo-adherence-computed-field.md
stakeholder_type: [project-contributor]
---

# Participant Embargo Consent Is Recorded per (Participant, Embargo), Against an Embargo Register on the Case

## Context and Problem Statement

Participant embargo consent was a hybrid of two records (ADR-0093, ADR-0118).
`CaseParticipant.accepted_embargo_ids` listed every embargo, active or proposed, the participant had accepted.
One scalar PEC state (`UNBOUND`, `INVITED`, `SIGNATORY`, `LAPSED`, `DECLINED`, `EXPIRED`, `UNBOUND_EXITED`) answered a single question: is the participant bound by the *active* embargo?
The two records disagreed (Concern #3884), and three reconciliation rules plus a first-proposal special case (MSM-07-003, PR #4002) kept them in step.

Revision 1 of this ADR replaced both with one consent row per (participant, embargo), and #4178 built it.
The docs work that followed (Concern #4284) showed that revision 1 left five problems:

1. "Never asked" was a missing row, so the machine had no named start state.
2. "Signatory", "lapsed" and "exited" were drawn as states, though they overlap and are only reads.
3. The case kept no record of its past embargoes: a superseded, rejected or terminated embargo vanished from it, so "every embargo on the case" could not be listed.
4. EM had its own transition table, which could disagree with the embargoes the case held.
   Rejecting one of two open proposals took EM to `NONE` with the other still open.
5. The case owner's activation rode on the same `Accept(Invite(EmbargoEvent))` every participant sends, with its meaning switched by who sent it (MSM-07-003/004).

The question: **what records hold a case's embargoes and each participant's consent to them, so that every state is named and written, and EM, "signatory" and "lapsed" are read from them?**

## Decision Drivers

- One fact, recorded once: two records of the same fact can disagree, and did.
- Every state a machine can be in is named and written; no state is inferred from a missing record.
- The case is the folder for everything that happened in its lifecycle, including every embargo proposed on it.
- The content gate (CM-10-004) must keep answering "is this participant bound by the embargo in force?" exactly.
- EP-05 containment (agreeing to N days is agreeing to every shorter period) must carry a participant over to a shorter revision.
- Names must not collide with the RM and EM models (`RM.ACCEPTED`) or with embargo expiry.
- The case must be rebuildable from its ledger (ADR-0124), so every change here is caused by a committed protocol message.
- Prototype stores only: no migration is owed (AGENTS.md persistence rule).

## Considered Options

- Keep the hybrid: the scalar plus `accepted_embargo_ids`, with the reconciliation rules.
- Make the list authoritative and drop the scalar, keeping no per-embargo state beyond acceptance.
- Record consent per (participant, embargo) with "not asked" as a missing row, and keep EM's own transition table (revision 1).
- Record consent per (participant, embargo) with every row written, against an embargo register on the case from which EM is derived.

## Decision Outcome

Chosen option: "Record consent per (participant, embargo) with every row written, against an embargo register on the case from which EM is derived", because it is the only option in which every state is named and written once and EM, "signatory" and "lapsed" are reads that cannot disagree with the records they read.

### The embargo register

`VulnerabilityCase.embargo_register` holds one **embargo register entry** `(embargo, status, replaces)` for every embargo ever proposed on the case.
`embargo` names the `EmbargoEvent`, carried inline when a sender carried it so a recipient can read the terms without a dereference (AKM-03-001).
Entries are appended and never removed.
`replaces` names the embargo an activated revision replaced.

| Status | Meaning |
|---|---|
| `PROPOSED` | An open proposal, awaiting the case owner's decision. |
| `ACTIVE` | In force. |
| `REJECTED` | The case owner declined the proposal. |
| `SUPERSEDED` | Was in force; a revision replaced it. |
| `CANCELLED` | Closed with no owner decision, because the embargo question became moot. |
| `TERMINATED` | Was in force when the case's embargo ended. |

| Trigger | Change |
|---|---|
| `PROPOSE` | new entry → `PROPOSED` |
| `ACTIVATE` | `PROPOSED → ACTIVE` |
| `REJECT` | `PROPOSED → REJECTED` |
| `SUPERSEDE` | `ACTIVE → SUPERSEDED`, in the same step as another entry's `ACTIVATE` |
| `TERMINATE` | `ACTIVE → TERMINATED`, with a reason: `END_TIME_REACHED`, `EARLY` or a threat signal |
| `CANCEL` | `PROPOSED → CANCELLED`, in the same step as a `TERMINATE`, or on a threat signal while no entry is `ACTIVE` |

`REJECTED`, `SUPERSEDED`, `CANCELLED` and `TERMINATED` are final.
`CANCEL` is legal only when the embargo question has become moot: in the same step as a `TERMINATE`, or when a threat signal (CS `P`, `X` or `A`) arrives while no entry is `ACTIVE` (EMB-16-001).
Every change to the register MUST keep these invariants, and a change that would break one is refused:

1. At most one entry is `ACTIVE` and at most one is `TERMINATED`, and never one of each.
2. A `SUPERSEDED` entry exists only alongside exactly one `ACTIVE` or `TERMINATED` entry.
3. No entry is `PROPOSED` while an entry is `TERMINATED`.
4. Once a step has left an entry `TERMINATED`, no later step adds or changes an entry.

A step is the whole change one entry causes, so `TERMINATE` and the `CANCEL` of every `PROPOSED` entry happen in one step and are checked together.

`PROPOSED` and `ACTIVE` keep the glossary's meaning of *Proposed Embargo* and *Active Embargo*.
The EM states use the same words for an aggregate over the whole register, so prose qualifies the bare words: "`EM.ACTIVE`" for the case, "register status `ACTIVE`" for one embargo.
`active_embargo` and `proposed_embargoes` become views of the register.

### EM is derived from the register

EM has no transition table of its own.
The EM transition table and `EMAdapter` are retired; their callers move to register triggers.
`CaseStatus` keeps its EM field as a copy that the case stamps from the register: at construction, at every register change and when a status is appended.
A received status can report EM but never move it: an asserted EM that differs from the register's is refused and the case's carried forward.

| `ACTIVE` entries | `PROPOSED` entries | `TERMINATED` entries | EM |
|---|---|---|---|
| 0 | 0 | 0 | `NONE` |
| 0 | ≥1 | 0 | `PROPOSED` |
| 1 | 0 | 0 | `ACTIVE` |
| 1 | ≥1 | 0 | `REVISE` |
| 0 | 0 | 1 | `EXITED` |

Every former EM transition is a register change: propose adds a `PROPOSED` entry, accept is `ACTIVATE` (with `SUPERSEDE` of any current `ACTIVE`), reject is `REJECT`, and terminate is `TERMINATE` with every open proposal `CANCELLED`.
Rejecting one of two open proposals leaves EM `PROPOSED` (or `REVISE`), because the other is still open.
An `ACTIVE` entry leaves that status only by `SUPERSEDE`, in the step that activates another entry, or by `TERMINATE`, after which invariant 4 allows no change.
So a case that has had an embargo in force never returns to `NONE` or `PROPOSED`.

### Participant embargo consent

`CaseParticipant.embargo_consents` holds one `EmbargoConsent(embargo_id, state, rsvp_deadline)` row for each entry in the embargo register.
The rows live on the participant record, not on the case; the case's full consent table is the union of its participants' rows.
`rsvp_deadline` is set only on an `INVITED` row, to that invitation's `Invite.end_time` when it has one (CM-28-001), and is cleared when the row leaves `INVITED`.
It replaces the single `CaseParticipant.invite_rsvp_deadline` field, so a participant can hold concurrent invitations with different deadlines.
Every row is written: when an embargo is proposed, every current participant gets an `UNINVITED` row for it; when a participant record is created, it gets an `UNINVITED` row for every entry already in the register.
A missing row is a defect, and reading one raises.
A participant that joins late stays `UNINVITED` on entries that are no longer in force; it is invited only to the `ACTIVE` embargo and to open revisions.

| State | Meaning |
|---|---|
| `UNINVITED` | Not asked about this embargo. The start state. |
| `INVITED` | Asked; no answer yet. Carries the invitation's RSVP deadline, if any. |
| `AGREED` | Agreed to this embargo: explicitly, as its proposer, by seeding (CM-14-003, CM-14-005), or by carry-over. |
| `DECLINED` | Explicitly refused this embargo, or withdrew from it (ADR-0093). |
| `TIMED_OUT` | Invited, and the RSVP deadline passed with no answer (ADR-0118, the pocket veto). Not a refusal. |

| Trigger | From | To |
|---|---|---|
| `INVITE` | `UNINVITED`, `DECLINED`, `TIMED_OUT` | `INVITED` |
| `AGREE` | `UNINVITED`, `INVITED`, `TIMED_OUT` | `AGREED` |
| `DECLINE` | `UNINVITED`, `INVITED`, `AGREED`, `TIMED_OUT` | `DECLINED` |
| `TIME_OUT` | `INVITED` | `TIMED_OUT` |
| `CARRY_OVER` | every state except `AGREED` | `AGREED` |

`AGREED` refuses `INVITE`, and `DECLINED` refuses `AGREE`: a participant that declined is invited again first.
`CARRY_OVER` is caused only by the activation of a revision that ends no later than the embargo it replaces, and applies only to participants whose row for the replaced embargo is `AGREED`.
It lifts a `DECLINED` row too: a participant that agreed to N days is bound for every shorter period (EP-05-001), and declining a shorter revision objects to losing time, not to keeping the embargo.
The decline itself stays in the ledger.

Rows for an entry in a final register status accept no trigger.
A late Accept of terms that are no longer current is answered with an invitation to the current embargo (EMB-17).

`ACCEPTED` became `AGREED` and `EXPIRED` became `TIMED_OUT`: `RM.ACCEPTED` and the `Accept` activity already use "accepted", and an embargo, not an invitation, is what expires.

### Signatory and lapsed are reads

Neither is a state, and neither is drawn on the state machine.

- **Signatory**: the participant's row for the register's `ACTIVE` entry is `AGREED`.
  The content gate (CM-10-004) reads `participant.is_signatory(case.active_embargo_id)` when an embargo is in force.
- **Lapsed**: an entry is `ACTIVE`, the participant's row for it is neither `AGREED` nor `DECLINED`, and, following `replaces` back from the `ACTIVE` entry, the first entry whose row is `AGREED` or `DECLINED` has an `AGREED` row.
  It was bound, and the embargo in force has since become something it did not agree to.
  A participant that withdrew from a later embargo, and so has a `DECLINED` row on it, has not lapsed when a further revision replaces that one.

After termination no entry is `ACTIVE`, so nobody is a signatory and nobody has lapsed.
`ParticipantStatus.consent`, the computed `embargo_adherence` and the stored scalar are removed.
The retired wire keys (`emConsentState`, `embargoAdherence`, `embargoConsentState`, `acceptedEmbargoIds`) are refused inbound by name (MV-11).

### The protocol messages that cause each change

Each change above is caused by one committed protocol message, and replay derives it (ADR-0124).

| Message | Register | Consent rows |
|---|---|---|
| `Invite(EmbargoEvent)` proposing a new embargo | `PROPOSE` | `UNINVITED` for every participant; the proposer `AGREE`; each invitee `INVITE` |
| `Invite(EmbargoEvent)` for an embargo already in the register: a re-invite, a late joiner's invite, or the fresh invite of EMB-17 | — | the invitee `INVITE` |
| a message that creates a participant record | — | the new participant `UNINVITED` for every register entry |
| case initialization seeding (CM-14-003, CM-14-005) | — | the case owner and the reporter `AGREE` on the `ACTIVE` entry |
| `Accept` of the full-case Invite (ADR-0121) | — | the joiner `AGREE` on the `ACTIVE` entry |
| `Accept(Invite(EmbargoEvent))`, from any participant, the owner included | — | the sender `AGREE` |
| `Reject(Invite(EmbargoEvent))` | — | the sender `DECLINE`; on the `ACTIVE` entry this is withdrawal, which also declines each open proposal the sender had agreed to |
| `Accept(EmbargoEvent, target=Case)`, the case owner only | `ACTIVATE`, and `SUPERSEDE` of any `ACTIVE` entry | the owner `AGREE` unless its row is already `AGREED`; `CARRY_OVER` when the revision ends no later than the one it replaces |
| `Reject(EmbargoEvent, target=Case)`, the case owner only | `REJECT` | — |
| `Remove(EmbargoEvent, target=Case)`, from the case owner, or from the CASE_MANAGER when delegated (ADR-0118, EMB-03-003) | `TERMINATE`, and `CANCEL` of each `PROPOSED` entry | — |
| a committed case status entry setting `P`, `X` or `A` | with an `ACTIVE` entry, `TERMINATE` (reason: threat signal) and `CANCEL` of each `PROPOSED` entry; with none, `CANCEL` of each `PROPOSED` entry | — |
| an invitation's RSVP deadline passing, committed as an entry (CM-28-009) | — | `TIME_OUT` on the invitee's row for that invitation's embargo |

An owner whose row for the proposal is `DECLINED` cannot activate it: `AGREE` refuses `DECLINED`, so replay refuses the activation, and the owner is invited again first.
The RSVP deadline belongs to one invitation (CM-28-001, CM-28-012), so its deadline is stored on that invitation's `INVITED` row, and a deadline passing times out only that row, never the participant's other `INVITED` rows.

The two-audience rule (MSM-07-003, MSM-07-004) is retired: the owner's decision for the case has its own activities, and `Accept`/`Reject(Invite(EmbargoEvent))` is always the sender's own consent.
The direct activation by `Add(EmbargoEvent, target=Case)` is retired, because adding an embargo to the case is what proposing does.

A termination `Remove` carries its reason in `content` as exactly `END_TIME_REACHED` or `EARLY`, checked at the parse edge; anything else is refused.
`summary` carries a human-readable account and is not read by the protocol.
Replay refuses `END_TIME_REACHED` on an entry published before the embargo's end time.
No new AS2 property is introduced.

An embargo reaches its end time through either of two requests, which share one idempotent termination path: the CASE_MANAGER's lazy check when it next handles the case, or an outside request such as a Sentinel monitoring embargo timers.
Both commit the CASE_MANAGER's `Remove(EmbargoEvent, target=Case)` with `content` `END_TIME_REACHED`.
A request that arrives after the entry is `TERMINATED` commits nothing and is answered as already done, so it never reaches the register and never breaks invariant 4.
The termination runs the full cascade: `TERMINATED` with its reason, every open proposal `CANCELLED`, EM `EXITED`, and the teardown announcement.

### Consequences

- Good, because every state is named and written: no machine starts from an absent record, and nothing that is only a read is drawn as a state.
- Good, because consent, the register and EM each have one record or one derivation, so "bound", "lapsed" and EM cannot disagree with what they read; the reconciliation rules, the MSM-07-003 special case and the EM transition table are deleted.
- Good, because the case keeps its whole embargo history, including rejected and cancelled proposals and the consent given to them.
- Good, because the owner's decisions for the case and each participant's own consent are different messages, so no handler branches on the sender to know what a message means.
- Good, because rejecting one of two open proposals no longer resets EM.
- Good, because an embargo that reaches its end time is recorded as ended, so the content gate stops withholding content under an embargo that has expired.
- Bad, because rows grow to participants × register entries per case and are never pruned; at the expected scale (up to hundreds of participants, a handful of embargoes per case) this is small.
- Bad, because the wire format changes: the consent row states, the owner's activation and rejection activities, and the termination `content` value.
  The prototype owes no compatibility.
- Bad, because stored `CaseParticipant` and `VulnerabilityCase` records in the old shape no longer load (`extra="forbid"`); the prototype keeps no migration.
- Bad, because every reader of EM state, the old scalar, `EMAdapter` and the two-audience rule must be revisited.

### Effect on earlier decisions

- ADR-0056 (`embargo_adherence` computed from PEC) is superseded: there is no scalar to derive it from.
- ADR-0048 (absence of embargo is not pre-consent) stands, now as `UNINVITED`.
- ADR-0091 (`NO_EMBARGO` → `UNBOUND`) is overtaken: `UNBOUND` is no longer a state.
- ADR-0093 (`DECLINE` legal from `SIGNATORY`) stands as `DECLINE` from an `AGREED` row; its "lapse at activation, never at proposal" rule stands as the lapsed read.
- ADR-0118 is superseded in its `UNBOUND_EXITED` half (termination is the register's fact); its `EXPIRED` half stands as `TIMED_OUT`, as do its decisions 3 and 4.
- ADR-0113 (relay through the CASE_MANAGER) is unchanged; its consent references now mean rows.
- ADR-0124 states the rule this ADR's changes rely on: every change is caused by a committed message, and the case is the replay of its ledger.

## Validation

- Unit tests drive each machine through every legal transition and assert each illegal one is refused.
- Register invariant tests assert that every refused combination raises, and that EM derives correctly for every combination of entry statuses.
- A test asserts every participant has exactly one row per register entry after propose, join and case setup.
- The rebuild-from-ledger test of ADR-0124 covers consent rows and the register.

## Pros and Cons of the Options

### Keep the hybrid

- Good, because nothing changes.
- Bad, because it is the design that produced Concern #3884 and needs three reconciliation rules plus a special case to stay coherent.

### List authoritative, scalar dropped

- Good, because there is one record.
- Bad, because the list records only acceptance: it cannot say declined versus timed out versus never asked, so those would need a second record again.

### Rows with "not asked" as a missing row, EM kept as its own machine (revision 1)

- Good, because consent has one record.
- Bad, because the start state is inferred from absence, and readers branch on `None`.
- Bad, because the case cannot list its embargoes, so nothing can check that each participant has a row for each.
- Bad, because EM's own table can disagree with the embargoes the case holds, and did.

### Written rows against an embargo register, EM derived

- Good, because each answer, including refusals, time-outs and never-asked, is stated once and written.
- Good, because EM, "signatory" and "lapsed" are reads over the register and the rows.
- Bad, because every reader of the former scalar, of EM and of `EMAdapter` must be revisited.

## More Information

Decided in the maintainer's design session of 2026-10-07, recorded in Concern #4284; implementation is tracked under epic #4283.
Revision 1 (2026-10-06) introduced the per-embargo rows with `INVITED`, `ACCEPTED`, `DECLINED` and `EXPIRED`, and left EM, the case's embargo history and the owner's activation as they were.

Generated spec requirements: `case-management.yaml` CM-18 and CM-10-001; `message-semantics-mapping.yaml` MSM-07; `embargo-policy.yaml` EP-05, EP-08, EP-09; `em-behavior.yaml` EMB-11, EMB-16, EMB-17 (updated by the implementation issues under #4283).
