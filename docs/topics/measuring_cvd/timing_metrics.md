---
stakeholder_type: [process-researcher]
level: 500
page_type: explanation
description: >
  Intervals, dwell times, margins, and spreads that the case ledger's timestamps make measurable within one case.
---

# Timing Metrics Within a Case

{% include-markdown "../../includes/not_normative.md" %}

This page proposes metrics for the time a Coordinated Vulnerability Disclosure (CVD) case takes between its events, not only the order of those events.
The measures in this section so far are about ordering: whether one event precedes another.
The case ledger records when each event was committed, which makes intervals, durations, and margins measurable within a single case.
The page is a draft research proposal for people who study the CVD process; none of it is normative, and no code computes these metrics today.

The page assumes the events and desiderata of [Desirable Histories](./desirable_histories.md) and of [Desiderata from the Process Models](./process_model_desiderata.md), which adds report, embargo, consent, and joining events to the original six.
It uses the notation of that page: $\mathbf{V}_i$ and $\mathbf{F}_i$ for vendor $i$'s awareness and fix readiness; $\mathbf{D}_k$ for deployer $k$'s deployment; $\mathbf{P}$, $\mathbf{X}$, and $\mathbf{A}$ for public awareness, a public exploit, and observed attacks; $\mathbf{E}$ and $\mathbf{E_x}$ for an embargo coming into force and ending.

Every metric below is either about the case or about one participant, because a case holds both kinds of state.
Public awareness, a public exploit, observed attacks, and the embargo belong to the case, and each happens once in it.
Report handling, fix readiness, deployment, and embargo consent belong to each participant, and each can happen once per participant.
[What a Case Records](./what_a_case_records.md) sets out that split, the ledger that stamps each change, and the gaps in what it stamps.

---

## Ordering is the sign of an interval

[Open Questions](./open_questions.md#what-timing-should-a-case-meet) names the gap this page addresses: the Case State (CS) model has a sense of order and no sense of time.
Two cases can both satisfy $\mathbf{F} \prec \mathbf{P}$, one with a month of warning for defenders and one with a minute.
The ordering measure scores them the same.

Every ordering desideratum $\sigma_1 \prec \sigma_2$ has a matching interval.
Write $t(\sigma)$ for the time event $\sigma$ occurred, and define the **margin** of the desideratum as

$$m(\sigma_1 \prec \sigma_2) = t(\sigma_2) - t(\sigma_1)$$

A positive margin means the desideratum held, and its size says by how much.
A negative margin means it failed, and its size says how badly.
The ordering measure keeps only the sign of $m$, so every timing metric below refines an ordering measure rather than replacing it.

---

## Which clock to use

The [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) writes one case ledger entry for each change it admits to the case, so the ledger is a time-ordered history of the case and the data source for nearly every metric on this page.
Each entry carries two clocks, the CASE_MANAGER's commit stamp and the sender's claimed time, described on [What a Case Records](./what_a_case_records.md#two-clocks).
The commit stamp is the default for every interval on this page, because it is one clock for the whole case.
Use the claimed time only where the lag between an event and its commit matters, and only for one participant's own events.
The difference between the two clocks on one entry is itself a measure, listed under process health below.

---

## Kinds of measure

Five shapes cover the proposed metrics.

| Shape | Definition | Example |
|---|---|---|
| Interval | Time from one event to another | Time from $\mathbf{V}_i$ to $\mathbf{F}_i$ |
| Margin | A signed interval for an ordering desideratum | $m(\mathbf{F} \prec \mathbf{P})$ |
| Dwell time | Total time the case spends in a state | Time with an embargo revision open |
| Spread | Time between the first and the last participant to reach the same event | First vendor's $\mathbf{F}$ to last vendor's $\mathbf{F}$ |
| Count or rate | How often something happens in one case | Embargo Invites that end in a pocket veto |

---

## Intake and triage

These intervals measure how fast a report becomes a case and a commitment.
They are per-participant, because Report Management (RM) is per-participant.

| Metric | Definition |
|---|---|
| Time to validate | $\mathbf{R}_i$ to $\mathbf{Va}_i$ |
| Time to accept | $\mathbf{Va}_i$ to $\mathbf{Ac}_i$ |
| Time to join, for an Invitee | Its Stub Invite to $\mathbf{J}_i$ |
| Time to judge, for an Invitee | Its Full-Case Invite to its answer, which is $\mathbf{Va}_i$ when it accepts (CM-11-011) |

An Invitee's $\mathbf{R}_i$ is its $\mathbf{J}_i$, because accepting the Stub Invite leaves it at RM Received (CM-11-001).
For an Invitee, then, time to validate is time to judge plus the wait between joining and receiving the Full-Case Invite.
The case owner's $\mathbf{R}$ and the reporter's $\mathbf{Ac}$ are seated when the case is created, so neither has a measurable time ([What a Case Records](./what_a_case_records.md#statuses-seated-at-case-creation)).

---

## Embargo

These metrics describe how an embargo is negotiated, how long it lasts, and how it ends.
Embargo Management (EM) is per-case, and Participant Embargo Consent (PEC) is per participant and per embargo.

| Metric | Definition |
|---|---|
| Time to embargo | Case creation to $\mathbf{E}$, usually zero because a case starts with an active embargo |
| Decision latency | A proposal to the case owner's decision on it |
| Revision count and time in Revise | How many revisions were proposed, and the dwell time in EM Revise |
| Planned and actual length | The embargo's end time minus $t(\mathbf{E})$, against $t(\mathbf{E_x})$ minus $t(\mathbf{E})$ |
| Time left at exit | The embargo's end time minus $t(\mathbf{E_x})$; zero when the end time was reached |
| Exit cause | Whether the end time was reached, or the embargo ended early, and for an early end its recorded cause |
| Response latency | Each participant's time from an embargo Invite to its answer |
| Pocket-veto rate | The share of embargo Invites that move to `TIMED_OUT` at their RSVP deadline, not counting those the case's close times out |
| Lapse count | How many participants lapsed when a revision with longer terms came into force |

Time left at exit and exit cause together separate the two ways an embargo ends.
An embargo that ends early because every fix is ready ends on its own terms.
An embargo that ends early because of a threat signal has a margin of about zero against the signal that ended it, slightly negative under commit stamps because the termination is committed after the status that reported the signal, and its time left at exit is what the threat cost.

---

## Fix and deployment

| Metric | Definition |
|---|---|
| Time to fix | $\mathbf{V}_i$ to $\mathbf{F}_i$, per vendor |
| Time to deploy | The first vendor's $\mathbf{F}$ to $\mathbf{D}_k$, per deployer |
| Notification spread | First vendor's $\mathbf{V}$ to last vendor's $\mathbf{V}$ |
| Fix spread | First vendor's $\mathbf{F}$ to last vendor's $\mathbf{F}$ |
| Trailing-vendor gap | Last vendor's $\mathbf{F}$ to $\mathbf{E_x}$; negative when the embargo ended before every fix was ready |

Time to deploy starts at the first vendor's $\mathbf{F}$ because that is the event the protocol gates deployment on: a deployer that is not also a vendor may move to $\mathbf{D}$ once any vendor in the case has a fix ready (CSB-15-004).
The case records no link from a deployer to the vendor whose fix it deployed, so a per-vendor time to deploy is not measurable from the case.

The spreads are Multi-Party CVD (MPCVD) measures with no counterpart in the single-vendor model.
[Benchmarking MPCVD](./benchmarking_mpcvd.md) aggregates per-vendor outcomes and leaves open how.
The fix spread and the trailing-vendor gap measure the cost of that aggregation directly: how long the slowest vendor holds the case, and whether the embargo waited.

---

## Disclosure margins

Each desideratum gives a margin.
These are the margins most directly tied to defender outcomes.

| Margin | What a positive value measures |
|---|---|
| $m(\mathbf{F} \prec \mathbf{P})$ | Lead time between a fix being ready and the vul being public |
| $m(\mathbf{D} \prec \mathbf{P})$ | Lead time between deployment and the vul being public |
| $m(\mathbf{E_x} \prec \mathbf{P_u})$ | Time a participant waited after the embargo before publishing |
| $m(\mathbf{P} \prec \mathbf{X})$ | Time between the vul being public and an exploit being public |
| $m(\mathbf{X} \prec \mathbf{A})$ | Time between a public exploit and observed attacks |

---

## Exposure

Some states are bad to be in, and the time spent in them matters more than the order of their entry.
Exposure metrics are dwell times in those states.

| Metric | Definition |
|---|---|
| Public exposure | Time during which $\mathbf{P}$ holds and $\mathbf{D}$ does not, per deployer |
| Exploit exposure | Time during which $\mathbf{X}$ holds and $\mathbf{D}$ does not, per deployer |
| Unfixed exposure | Time during which $\mathbf{P}$ holds and $\mathbf{F}$ does not, per vendor |

[Open Questions](./open_questions.md#what-timing-should-a-case-meet) proposes that a deployer's vulnerability management is effective when the lag from $\mathbf{F}$ to $\mathbf{D}$ is shorter than the lag from $\mathbf{F}$ to $\mathbf{A}$.
Exploit exposure measures the same race as a duration.

---

## Closure and case administration

| Metric | Definition |
|---|---|
| Case duration | Case creation to the case being fully closed |
| Time open after disclosure | $\mathbf{P}$ to the case being fully closed |
| Embargo Invites timed out at close | Embargo Invites still awaiting a reply that the owner's close moves to `TIMED_OUT` (CM-23-014) |
| Ownership transfer latency | An offer to transfer case ownership to its acceptance, rejection, withdrawal, or expiry |

---

## Process health

These metrics describe the protocol's own operation in a case, not the CVD outcome.
They help separate a slow case from a case whose messages went missing.

| Metric | Definition |
|---|---|
| Gap rate | Received RM declarations that skip a step, which the CASE_MANAGER accepts and notes on the case (RSH-06-004) |
| Regression count | Received RM declarations that move backward, which the CASE_MANAGER refuses and notes (RSH-06-002) |
| Refusal count | Assertions the CASE_MANAGER refused rather than admitted |
| Replay count | Ledger replays requested by participants whose replica fell behind |
| Clock skew | Commit stamp minus claimed time, per participant |

A gap is a forward move whose intermediate step the CASE_MANAGER never saw: either a message was lost, or the participant took the step locally and declared only its latest state.
A rising gap rate is therefore a prompt to look for lost messages, not proof of them.
A large clock skew for one participant means its claimed times cannot be trusted for intervals.

---

## Gaps in the data

Most of the metrics above can be computed from the case ledger as it is.
Some cannot, because the event is stamped late, stamped with the creation time, or not ledgered at all.
[What a Case Records](./what_a_case_records.md#data-gaps) lists those gaps, and each metric that depends on one inherits it.

---

## Intervals to events that have not happened

Many cases never see $\mathbf{X}$ or $\mathbf{A}$, and an open case has not yet closed.
An interval that ends at an event that has not happened is **censored**: it is known to be at least as long as the case has run, not missing.
Treating censored intervals as missing biases every average toward the cases that finished.
Across cases, censored intervals call for survival-analysis methods, such as a Kaplan–Meier estimate of time to fix, and medians rather than means.

---

## Relation to service level expectations

[Open Questions](./open_questions.md#what-timing-should-a-case-meet) and [Policy Formalization](../other_uses/policy_formalization.md) sketch Service Level Expectations (SLEs): timers that start and stop on transitions, such as a bound on the time from $\mathbf{V}$ to $\mathbf{F}$.
An SLE is a threshold on one of the intervals above.
Defining the intervals first lets an SLE be stated as a number against a metric that already has a definition.
It also lets a program report the distribution of an interval across its cases, rather than only how often it met a threshold.

---

## In a two-party case

A two-party case, with one reporter and one vendor, is the special case of the same model, not a separate one.
Most metrics carry over unchanged: the vendor's intake and triage intervals, every embargo metric, time to fix, the disclosure margins that do not involve $\mathbf{D}$, closure, and process health.
The spreads collapse: with one vendor, notification spread and fix spread are zero, and the trailing-vendor gap is the time from the vendor's own $\mathbf{F}$ to $\mathbf{E_x}$.
The deployment metrics disappear unless some participant holds the deployer role.
Time to deploy, the $\mathbf{D}$ margins, and public and exploit exposure all need a participant with a deployment state, and a vendor has one only when it is also a deployer (SDO-03-002).

---

## Summary

| Area | Representative metrics |
|---|---|
| Intake and triage | Time to validate, accept, judge, join |
| Embargo | Decision latency, revisions, planned and actual length, time left at exit, exit cause, response latency, pocket-veto rate |
| Fix and deployment | Time to fix and deploy; notification spread, fix spread, trailing-vendor gap |
| Disclosure margins | $m(\mathbf{F} \prec \mathbf{P})$, $m(\mathbf{D} \prec \mathbf{P})$, $m(\mathbf{P} \prec \mathbf{X})$, and the margin of every other desideratum |
| Exposure | Time with $\mathbf{P}$ or $\mathbf{X}$ and no $\mathbf{D}$ |
| Closure | Case duration, time open after disclosure, embargo Invites timed out at close, transfer latency |
| Process health | Gap rate, regressions, refusals, replays, clock skew |

## Further reading

- [Desiderata from the Process Models](./process_model_desiderata.md) — the extended events and orderings whose margins this page measures.
- [Desirable Histories](./desirable_histories.md) — the original twelve desiderata.
- [What a Case Records](./what_a_case_records.md) — the per-case and per-participant split, the two clocks, and the data gaps.
- [Open Questions](./open_questions.md) — the ordering-versus-timing limitation and the first sketch of service level expectations.
- [The CASE_MANAGER and the Case Ledger](../case_lifecycle/case_manager_and_ledger.md) — the ledger that supplies every timestamp.
