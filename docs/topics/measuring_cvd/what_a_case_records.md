---
stakeholder_type: [process-researcher]
level: 400
page_type: explanation
subject: neutral
description: >
  The events that a Vultron case records, which events belong to the case or to one participant, the two times on each entry, and the data gaps.
---

# What a Case Records

{% include-markdown "../../includes/not_normative.md" %}

This page describes the record that a Vultron case keeps.
Every measure in the Measuring CVD section uses this record as its data.
The page tells which events the case records, and whether each event belongs to the case or to one participant.
The page also tells which times the case puts on each event, where the record has gaps, and which participants can see which events.
The page is for people who measure Coordinated Vulnerability Disclosure (CVD) from cases.
These people need to know the limits of the data before they calculate.

Vultron models Multi-Party CVD (MPCVD) as the general case.
A two-party case has one reporter and one vendor.
A two-party case is a special case of the same record, not a different record.
The [last section](#in-a-two-party-case) tells what changes in a two-party case.

---

## Per-case and per-participant state

The state of a case is the set of facts that the case tracks, for example whether the vul is public.
An event is a change in one of these facts, for example the change from "not public" to "public".
The table below gives the events that the Measuring CVD pages use, with the symbol for each event.

{% include-markdown "./_case_events.md" %}

Each participant in a case has one or more [roles](../../reference/glossary.md#cvd-roles-and-participants), such as reporter, vendor, deployer, or coordinator.

A case holds two kinds of state:

- **Participant-agnostic state** belongs to the case. The case has one copy, and that copy is the same for every participant.
- **Participant-specific state** belongs to one participant. Each participant has its own copy, and one participant's copy does not change when another participant's copy changes.

The [Glossary](../../reference/glossary.md#state-machines-and-status) defines both terms.
The table below shows which kind each part of the case state is.

| State | Belongs to | Held by |
|---|---|---|
| Public awareness, public exploit, attacks observed (PXA) | The case | Every case, once (SDO-03-001) |
| Embargo Management (EM) | The case | Every case, once, derived from its embargo register (ADR-0122) |
| Report Management (RM) | Each participant | Every participant (SDO-03-002) |
| Vendor fix path: vendor awareness and fix readiness (VF) | Each vendor | Every participant with the Vendor role (SDO-03-002) |
| Fix deployment (D) | Each deployer | Every participant with the Deployer role (SDO-03-002) |
| Participant Embargo Consent (PEC) | Each participant, per embargo | One row for every entry in the embargo register (CM-18-001) |

!!! note "Embargo register and consent rows"

    The embargo register is the list of every embargo that anyone proposed for the case.
    Each entry in the register has a status, such as proposed, active, or ended.
    The case derives its EM state from the statuses in the register.
    A consent row records the answer of one participant to one embargo in the register.
    The answer is one of `UNINVITED`, `INVITED`, `AGREED`, `DECLINED`, or `TIMED_OUT` (CM-18-001).
    A participant with an `AGREED` row for the active embargo is a signatory of that embargo.

A participant that is both a vendor and a deployer holds a fix path and a deployment state.
A reporter, a coordinator, or an observer holds only an RM state and consent rows.

The kind of state controls how many times an event can occur in one case.
Public awareness ($\evP$) is participant-agnostic, so $\evP$ occurs at most once in a case.
Fix readiness ($\evF$) is participant-specific, so $\evF$ can occur once for each vendor.
A case with ten vendors can have ten $\evF$ events.

The [Foundations](foundations/index.md) model gives each case six events, and each event occurs once.
That assumption is correct for the participant-agnostic events $\evP$, a public exploit ($\evX$), and observed attacks ($\evA$).
That assumption is not correct for the participant-specific events vendor awareness ($\evV$), $\evF$, and fix deployment ($\evD$).
These events can occur more than once in a case with more than one vendor or deployer.

The case does not link a deployer to a vendor.
A deployer that is not also a vendor can record a deployment after any vendor in the case has a fix ready (CSB-15-004).
The case does not record which vendor made the fix that the deployer deployed.

---

## Events a case records

The [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) is the participant that holds the canonical record of the case.
This record is the case ledger.
Participants send their changes to the CASE_MANAGER as protocol messages.
The CASE_MANAGER checks each change, and admits the change to the case only if the change is valid.
For each admitted change, the CASE_MANAGER writes one case ledger entry (CLP-07-013).
The CASE_MANAGER writes the entries in the order that it admits the changes.
The CASE_MANAGER then sends a copy of each entry to the other participants.
The copy of the ledger that a participant holds is its replica.
A decision that changes nothing is not an entry.
For example, the CASE_MANAGER does not write an entry when it sees that a deadline has passed and nothing else changes.

The table below names each entry by its protocol message.
A protocol message has the form of an ActivityStreams activity: a verb and the object of the verb.
For example, `Add(ParticipantStatus)` adds a new status to a participant.
The [message reference](../../reference/messages/index.md) describes each message.
The case owner is the participant that created the case, or that later received ownership of the case.

| Event | Belongs to | Recorded as |
|---|---|---|
| Case creation | The case | The first entry of the ledger (the genesis entry), the CASE_MANAGER's `Create(VulnerabilityCase)` |
| A participant joins | The participant | The participant's acceptance of the invitation to the case, and the CASE_MANAGER's record of the new participant |
| Report received, valid, accepted, deferred, closed | The participant | The participant's status update, `Add(ParticipantStatus)`, or the act that changes the participant's RM state: joining, validating, deferring, or leaving the case |
| Vendor awareness, fix ready | The vendor | The vendor's status update, `Add(ParticipantStatus)`, with a new fix-path state |
| Fix deployed | The deployer | A status update with a new deployment state, sent by the deployer, or by the CASE_MANAGER or the case owner for the deployer |
| Public awareness, public exploit, attacks observed | The case | The CASE_MANAGER's own `Add(CaseStatus)`, written when the CASE_MANAGER accepts a participant's report as the state of the case (adoption) |
| Embargo proposed, accepted, rejected, ended | The case | The proposal's `Invite(EmbargoEvent)`, the answers to the proposal, and the termination's `Remove(EmbargoEvent)` |
| Consent given, refused, or timed out | The participant, per embargo | The participant's `Accept` or `Reject` of the embargo Invite, or the CASE_MANAGER's `Update(EmbargoConsent)` |
| A note added or removed | The case | The `Add` or `Remove` of the note |
| Case ownership transferred | The case | The transfer offer, the answer to the offer, and the CASE_MANAGER's `Update(VulnerabilityCase)` that names the new owner |

The ledger is thus a history of the case in time order.
The ledger records every change to report status, embargo, consent, participants, and case status.

The ledger is a hash chain: each entry includes the hash of the entry before it.
Thus no one can change an earlier entry without detection.
Each entry has a log index, which is the position of the entry in the hash chain.
The log index gives the authoritative order in which the CASE_MANAGER admitted the changes (CLP-14-001).

---

## Two clocks

Each ledger entry carries two times.

| Time | Where it is | What it means |
|---|---|---|
| Commit stamp | The `published` field of the entry, equal to its `receivedAt` | The time on the CASE_MANAGER's clock when the CASE_MANAGER committed the entry (CLP-14-002); the commit stamp never decreases in log order (CLP-14-003) |
| Claimed time | The `published` field of the activity in the entry | The time that the sender put on its activity; every activity must carry a claimed time (CLP-15-006) |

All commit stamps in a case come from one clock, the CASE_MANAGER's clock.
Thus the interval between any two commit stamps in a case is a valid comparison.
A commit stamp tells you when the CASE_MANAGER learned of an event.
The CASE_MANAGER can learn of an event after the event occurred.

A claimed time comes from the clock of the sender.
The sender should use the time that the event occurred, not the time that the sender sent or sent again the message (CLP-15-004).
The claimed times of one participant must not decrease across activities that depend on each other (CLP-15-003).
The claimed times of two different participants come from two different clocks, so these claimed times can disagree.

The CASE_MANAGER records each claimed time as received, and does not correct it.
The reason is that the ledger records what the CASE_MANAGER observed (CLP-15-005).
The ledger does not try to rebuild the order of events at each participant.

Some entries are written by the CASE_MANAGER itself, for example an adopted case status or an embargo termination.
For these entries, the commit stamp and the claimed time both come from the CASE_MANAGER's clock.

---

## Data gaps

Most measures need only the case ledger.
The gaps in this section limit some measures.

### Statuses seated at case creation

The case owner creates the case when it receives the report.
The [RM model](../process_models/rm/index.md) gives each participant a report state, such as Received, Valid, Accepted, Deferred, or Closed.
The creation sequence puts the case owner at RM Received (CM-14-009), and puts the reporter at RM Accepted (CM-14-012).
The CASE_MANAGER commits these two statuses during the creation sequence.
Thus the commit stamps of these two statuses show the creation time, not the time of each event.

For the case owner, the time of report receipt ($\evR$) is the creation time.
The time that the case owner actually received the report stays with the case owner, outside the case ledger.
For the reporter, report acceptance ($\evAc$) is not a decision, so $\evAc$ has no interval to measure.
The later validation and acceptance by the case owner are separate entries.
Thus the time from case creation to the validation and acceptance by the case owner is measurable.

### Clock decisions are stamped when the CASE_MANAGER next acts

Two kinds of change occur because a deadline passes:

- An embargo reaches its end time.
- An embargo Invite reaches its RSVP deadline, and the invitee has not answered. The RSVP deadline is the time by which the invited participant must answer.

A timer does not start these changes.
The CASE_MANAGER ends an embargo at the end time in one of two conditions (EMB-13-003):

- The CASE_MANAGER next handles the case.
- An outside service, such as a monitor of embargo timers, tells the CASE_MANAGER to end the embargo.

The CASE_MANAGER times out an unanswered Invite when it next processes an embargo activity for the case (CM-28-015).

The CASE_MANAGER stamps each of these changes when it makes the change.
This time can be much later than the deadline.
The claimed time of the termination is also the time that the CASE_MANAGER handled the case, not the end time.

The record keeps each deadline.
The embargo carries its end time, and the Invite carries its RSVP deadline.
Each termination records its reason, and `END_TIME_REACHED` is the reason for an embargo that ended because its end time passed.
For an `END_TIME_REACHED` termination, the end time on the embargo is the actual end of the embargo.
The commit stamp of the termination is only the latest possible end.

### An ownership-transfer expiry is not ledgered

An offer to transfer case ownership carries an end time.
When the end time passes, the CASE_MANAGER treats the offer as closed.
The CASE_MANAGER does not record an entry for the expiry, because no participant's record changes (CM-21-017, ADR-0152).
A measure of the time from an offer to its expiry must get the expiry time from the end time on the ledgered offer.

### The case's public state is stamped when it is adopted

A participant can learn of public awareness, a public exploit, or attacks.
The participant then reports this information in its own status update.
The CASE_MANAGER ledgers the status update with the claimed time of the participant.

The PXA state of the case changes only when the CASE_MANAGER adopts the report.
To adopt the report, the CASE_MANAGER commits its own `Add(CaseStatus)`.
Both times on the `Add(CaseStatus)` entry come from the CASE_MANAGER's clock at adoption.

Thus the case-level time of $\evP$, $\evX$, or $\evA$ is the time that the CASE_MANAGER adopted the report.
The case-level time is not the time that a participant first reported the event.
The first report is in the status entries of the participants.
These status entries come before the `Add(CaseStatus)` entry in the ledger.

### Events outside the protocol are stamped when reported

Some events are protocol acts, for example an acceptance, an embargo step, or a join.
For a protocol act, the event and its commit occur at almost the same time.

The events $\evX$ and $\evA$ occur outside the protocol.
A participant can report $\evX$ or $\evA$ a long time after the event.
The record does not show the length of this delay.

### Refusals and replays are not on the ledger

When the CASE_MANAGER does not admit a change, it sends a refusal notice to the participant that sent the change (CLP-05-001).
A refusal notice is about the ledger, not about the case.
A replica that misses entries can ask the CASE_MANAGER to send the entries again, which is a replay.
A request for a replay is also about the ledger, not about the case.
Thus the CASE_MANAGER does not ledger refusal notices or replay requests (CLP-02-012, CLP-02-013).
A count of refusals or replays must use the CASE_MANAGER's own logs or its outbox.

### Embargo records carry no times of their own

An entry in the embargo register holds a status.
A participant's consent row also holds a status.
Neither record holds the time of the step that set the status.

These records do hold two deadlines: the end time of an embargo, and the RSVP deadline of an Invite.
The time of each step is only in the ledger entry that recorded the step.
Thus every embargo measure must connect the embargo register and the consent rows to the ledger entries.

---

## Who observes what

The CASE_MANAGER holds the complete ledger.
Every other participant holds a replica of the ledger.
A participant's replica receives ledger entries while the participant is active in the case (CM-10-004).
A participant is active after it joins the case, until it is removed.
While an embargo is active, a participant is also active only if it agreed to that embargo.

These conditions stop or pause the flow of entries to a participant:

- An embargo is active, and the participant has not agreed to it. The participant receives no entries until it agrees or the embargo ends. Then the participant receives every entry that it did not get, in order (CM-10-005, CM-10-006).
- The participant's report is closed. The participant receives no entries after the entries that record its closure (CM-23-004).

Thus a participant's replica holds all or part of the CASE_MANAGER's ledger.
Only the CASE_MANAGER's ledger is complete.

The ledger can only be as accurate as the reports of the participants.
The table below shows the source of each kind of event.

| Event | Source |
|---|---|
| Report handling, embargo steps, consent, joining | Protocol acts. The ledger records each act when it occurs. |
| Fix readiness | The vendor's own report |
| Deployment | The deployer's own report, or a report for the deployer by the CASE_MANAGER or the case owner. Deployment is the event that participants report least often. |
| Public exploit, attacks observed | Events outside the protocol. The case learns of them only when a participant reports them. |

Parties outside the case see only what the participants publish.
[Observing Skill](observing_skill.md) shows what the public record alone can tell.

---

## In a two-party case

A two-party case has one reporter and one vendor.
The participant-agnostic state of a two-party case is the same as in any case: one PXA state and one EM state.

The participant-specific state of a two-party case has two copies:

- The reporter holds an RM state and consent rows.
- The vendor holds an RM state, a fix path, and consent rows.

In a two-party case, $\evV$ and $\evF$ each occur at most once, because the case has one vendor.
Thus the six-event model of the [Foundations](foundations/index.md) is almost correct for a two-party case.

Deployment ($\evD$) is the exception.
The case records $\evD$ only in one of two conditions:

- The vendor also has the Deployer role.
- A deployer joins the case. The case then has three participants and is no longer a two-party case.

---

## Reading the record

A measure starts with the CASE_MANAGER's ledger.
If the CASE_MANAGER's ledger is not available, the measure merges the replicas of the participants.
For embargo times, the measure connects the embargo register and the consent rows to the ledger entries that set them.

!!! info "In the reference implementation"

    The demo scenarios write each actor's copy of the ledger as JavaScript Object Notation (JSON) Lines files, under `devlogs/<demo>/<actor>/` (`vultron/demo/helpers/ledger_dump.py`).
    Each file holds one actor's copy of the ledger for one case.
    `vultron-demo-report` (`vultron/demo/report.py`) reads these files and merges the replicas into one timeline for each case, in log order (DRPT-02).
    The report also shows which actors' replicas hold each entry.
    Each timeline event shows the actor, the semantic type, the target, the commit stamp, and the state changes that the entry records.

## Further reading

- [The CASE_MANAGER and the Case Ledger](../case_lifecycle/case_manager_and_ledger.md) — the ledger that supplies every entry and every time on this page.
- [Desiderata from the Process Models](process_model_desiderata.md) — the orders of these events that a case should achieve.
- [Timing Metrics Within a Case](timing_metrics.md) — the intervals between these events that the two clocks make measurable.
- [Open Questions](open_questions.md) — the questions about measuring CVD that are still open.
