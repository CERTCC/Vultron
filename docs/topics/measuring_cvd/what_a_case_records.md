---
stakeholder_type: [process-researcher]
level: 400
page_type: explanation
description: >
  The events a Vultron case records, whether each belongs to the case or to one participant, the two clocks on each record, and the gaps.
---

# What a Case Records

{% include-markdown "../../includes/not_normative.md" %}

This page describes the record a Vultron case keeps, which is the data every measure in this section works from.
It covers which events the case records, whether each belongs to the case or to one participant, which clocks stamp them, where the record has gaps, and who can see which parts of it.
It is for people who want to measure Coordinated Vulnerability Disclosure (CVD) from cases, and who need to know what the data can and cannot say before they compute anything.

Vultron models Multi-Party CVD (MPCVD) as the general case.
A two-party case, with one reporter and one vendor, is a special case of the same record, not a separate one, and the [last section](#in-a-two-party-case) says what changes in it.

---

## Per-case and per-participant state

A case holds two kinds of state.
**Participant-agnostic state** belongs to the case as a whole and is the same for every participant.
**Participant-specific state** belongs to one participant, and each participant holds its own copy independently of the others ([Glossary](../../reference/glossary.md#state-machines-and-status)).

| State | Belongs to | Held by |
|---|---|---|
| Public awareness, public exploit, attacks observed (PXA) | The case | Every case, once (SDO-03-001) |
| Embargo Management (EM) | The case | Every case, once, derived from its embargo register (ADR-0122) |
| Report Management (RM) | Each participant | Every participant (SDO-03-002) |
| Vendor fix path: vendor awareness and fix readiness (VF) | Each vendor | Every participant with the Vendor role (SDO-03-002) |
| Fix deployment (D) | Each deployer | Every participant with the Deployer role (SDO-03-002) |
| Participant Embargo Consent (PEC) | Each participant, per embargo | One row for every entry in the embargo register (CM-18-001) |

A participant that is both a vendor and a deployer holds both a fix path and a deployment state.
A reporter, a coordinator, or an observer holds only its RM state and its consent rows.

The split matters for measurement because it decides how often an event can happen.
A participant-agnostic event, such as public awareness $\mathbf{P}$, happens once per case.
A participant-specific event, such as fix readiness $\mathbf{F}$, happens once per vendor, so a case with ten vendors has ten of them.
The [Foundations](foundations/index.md) model treats a case as six events that each happen once, which is exact only for the participant-agnostic three.

The case does not pair a deployer with a vendor.
A deployer that is not also a vendor may record deployment once any vendor in the case has a fix ready (CSB-15-004), and nothing records whose fix it deployed.

---

## Events a case records

The [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) is the participant that holds the case's canonical record.
It writes one case ledger entry for each change it admits to the case, in the order it admits them (CLP-07-013).
A decision that changes nothing, such as noticing that a deadline has passed, is not an entry.

| Event | Belongs to | Recorded as |
|---|---|---|
| Case creation | The case | The genesis entry, the CASE_MANAGER's `Create(VulnerabilityCase)` |
| A participant joins | The participant | Its acceptance of the invitation to the case, and the CASE_MANAGER's record of the new participant |
| Report received, valid, accepted, deferred, closed | The participant | Its status update, `Add(ParticipantStatus)`, or the act that moves its RM state, such as joining, validating, deferring, or leaving the case |
| Vendor awareness, fix ready | The vendor | Its status update, `Add(ParticipantStatus)`, with a new fix-path state |
| Fix deployed | The deployer | A status update with a new deployment state, sent by the deployer or on its behalf by the CASE_MANAGER or the case owner |
| Public awareness, public exploit, attacks observed | The case | The CASE_MANAGER's own `Add(CaseStatus)`, when it adopts what a participant reported |
| Embargo proposed, accepted, rejected, ended | The case | The proposal's `Invite(EmbargoEvent)`, its answers, and the termination's `Remove(EmbargoEvent)` |
| Consent given, refused, or timed out | The participant, per embargo | Its `Accept` or `Reject` of the embargo Invite, or the CASE_MANAGER's `Update(EmbargoConsent)` |
| A note added or removed | The case | The note's `Add` or `Remove` |
| Case ownership transferred | The case | The transfer's offer, its answer, and the CASE_MANAGER's `Update(VulnerabilityCase)` naming the new owner |

The ledger is therefore a time-ordered history of the case, covering every report, embargo, consent, participant, and case status change.
Its order is the log index, each entry's position in the hash chain, which is the authoritative order of admission (CLP-14-001).

---

## Two clocks

Each entry carries two times.

| Time | Where it is | What it means |
|---|---|---|
| Commit stamp | The entry's own `published`, equal to its `receivedAt` | The CASE_MANAGER's clock when it committed the entry (CLP-14-002); non-decreasing in log order (CLP-14-003) |
| Claimed time | The `published` of the activity the entry carries | The time the sender put on its activity, which every activity must carry (CLP-15-006) |

The commit stamp comes from one clock, so the interval between any two entries is comparable.
It records when the CASE_MANAGER learned of an event, which can be later than when the event happened.

The claimed time is the sender's own clock.
A participant should set it to when the event happened, not when it sent or retried the message (CLP-15-004).
It must be monotonic only across one participant's causally related activities (CLP-15-003), so two participants' claimed times can disagree.
The CASE_MANAGER records it as received, without correcting it, because the ledger is what the CASE_MANAGER observed, not a reconstruction of each participant's order (CLP-15-005).

For an entry the CASE_MANAGER writes itself, such as an adopted case status or an embargo it ends, both times come from the CASE_MANAGER's clock.

---

## Data gaps

Most measures can be computed from the case ledger as it is.
The gaps below limit some of them.

### Statuses seated at case creation

The case owner creates the case on receiving the report, and the creation sequence seats it at RM Received (CM-14-009) and the reporter at RM Accepted (CM-14-012).
Those statuses are committed in the creation sequence, so their commit stamps carry the creation time, not the time of the event.
The case owner's $\mathbf{R}$ is the creation time, and the report's own received time lives with the case owner, outside the case ledger.
The reporter's $\mathbf{Ac}$ is not a decision at all, so it has no interval to measure.
The case owner's later validation and acceptance are entries of their own, so its time to validate and time to accept are measurable from the creation time.

### Clock decisions are stamped when the CASE_MANAGER next acts

Two kinds of change happen because a deadline passes: an embargo reaching its end time, and an embargo Invite reaching its RSVP deadline with no answer.
Neither runs on a timer.
The CASE_MANAGER ends an embargo at its end time when it next handles the case, or when something outside asks it to, such as a monitor of embargo timers (EMB-13-003).
It times out an unanswered Invite when it next processes an embargo activity for the case (CM-28-015).

Both changes are stamped when the CASE_MANAGER makes them, which can be well after the deadline.
The termination's claimed time is also the handling time, not the end time.
The deadline itself is on the record: the embargo carries its end time, and the Invite carries its RSVP deadline.
A measure of when an embargo actually ended should read the end time from the embargo for an `END_TIME_REACHED` termination, and treat the stamp as an upper bound.

### An ownership-transfer expiry is not ledgered

An offer to transfer case ownership carries an end time.
When it passes, the CASE_MANAGER treats the offer as closed, but it records no entry, because no participant's record changes (CM-21-017, ADR-0152).
The expiry time is the offer's end time, read from the ledgered offer, and a measure of transfer latency has to derive it.

### The case's public state is stamped when it is adopted

A participant that learns of public awareness, a public exploit, or attacks reports it in its own status update, which is ledgered with that participant's claimed time.
The case's own PXA state changes only when the CASE_MANAGER adopts the report and commits its own `Add(CaseStatus)`.
That entry's times are both the CASE_MANAGER's clock at adoption.
The case-level time of $\mathbf{P}$, $\mathbf{X}$, or $\mathbf{A}$ is therefore when the CASE_MANAGER adopted it, not when a participant first reported it.
The earliest report is recoverable from the participants' own status entries, which come first in the ledger.

### Events outside the protocol are stamped when reported

For protocol acts, such as an acceptance, an embargo step, or a join, the event and its commit are close in time.
For $\mathbf{X}$ and $\mathbf{A}$, which happen outside the protocol, the lag between occurrence and a participant's report of it can be long, and nothing measures it.

### Refusals and replays are not on the ledger

A refusal notice and a replica's request for a replay are about the ledger, not about the case, so neither is ledgered (CLP-02-012, CLP-02-013).
A count of refusals or replays needs the CASE_MANAGER's own logs or its outbox, not the case ledger.

### Embargo records carry no times of their own

An entry in the embargo register and a participant's consent row hold a status, and no time of the step that set it.
They do carry times about the embargo: an embargo's end time, and an Invite's RSVP deadline.
Their timing comes only from the ledger entries that recorded each step.
Every embargo measure therefore needs a join from the register and the consent rows back to the ledger.

---

## Who observes what

The CASE_MANAGER holds the complete ledger.
Every other participant holds a replica, which receives the ledger's entries while the participant is active in the case (CM-10-004).
While an embargo is active, a participant that has not agreed to it receives nothing until it agrees or the embargo ends, and then receives every entry it missed, in order (CM-10-005, CM-10-006).
A participant whose report is closed stops receiving entries after those that record its closure (CM-23-004).
So a participant's replica is the CASE_MANAGER's ledger, or a part of it, and only the CASE_MANAGER's copy is complete.

What enters the ledger is only as good as what participants report.

- Report handling, embargo steps, consent, and joining are protocol acts, so the ledger records them as they happen.
- Fix readiness is the vendor's own report.
- Deployment is the deployer's own report, or one made on its behalf, and is the event least likely to be reported at all.
- A public exploit and observed attacks happen outside the protocol, and reach the case only when a participant reports them.

Parties outside the case see only what its participants publish.
[Observing Skill](observing_skill.md) shows what can be inferred from that public record alone.

---

## In a two-party case

A two-party case has one reporter and one vendor.
Its participant-agnostic state is the same as in any case: one PXA state and one EM state.
Its participant-specific state is two copies: the reporter's RM state and consent rows, and the vendor's RM state, fix path, and consent rows.
Every participant-specific event happens at most once for the vendor, so the six-event model of the [Foundations](foundations/index.md) fits it closely.
Deployment is the exception: the case records it only if the vendor also holds the Deployer role, or if a deployer joins and the case stops being two-party.

## Reading the record

A measure reads the case's ledger, merges what replicas hold where it has no CASE_MANAGER copy, and joins the embargo register and consent rows back to the entries that set them.

!!! info "In the reference implementation"

    The demo scenarios write each actor's copy of the ledger as JavaScript Object Notation (JSON) Lines, one file per actor and case, under `devlogs/<demo>/<actor>/` (`vultron/demo/helpers/ledger_dump.py`).
    `vultron-demo-report` (`vultron/demo/report.py`) reads those files, merges the replicas into one timeline per case in log order, and shows which actors' replicas hold each entry (DRPT-02).
    Each timeline event carries its actor, semantic type, target, commit stamp, and the state changes it records.

## Further reading

- [The CASE_MANAGER and the Case Ledger](../case_lifecycle/case_manager_and_ledger.md) — the ledger that supplies every entry and timestamp on this page.
- [Desiderata from the Process Models](process_model_desiderata.md) — the orderings over these events that a case should achieve.
- [Timing Metrics Within a Case](timing_metrics.md) — the intervals between these events that the two clocks make measurable.
- [Open Questions](open_questions.md) — what measuring CVD still leaves open.
