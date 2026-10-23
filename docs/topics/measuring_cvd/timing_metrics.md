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
The page is a draft research proposal for people who study the CVD process.
No part of the page is normative, and no code calculates these metrics today.

A desideratum is an order of two events that a case should achieve.
For example, the fix should be ready before the vul is public.
[Desirable Histories](./desirable_histories.md) gives the twelve original desiderata.
[Desiderata from the Process Models](./process_model_desiderata.md) adds desiderata about report, embargo, consent, and joining events.

The page uses the events and symbols of [What a Case Records](./what_a_case_records.md):

{% include-markdown "./_case_events.md" %}

The page also uses participant publication ($\mathbf{P_u}$), the public awareness that comes from a coordinated publication by a participant ([Desiderata from the Process Models](./process_model_desiderata.md#splitting-events-by-cause)).

Each metric on this page is about the case, or about one participant.
Some events belong to the case and occur at most once in the case.
These events are public awareness, a public exploit, observed attacks, and the start and end of the embargo.
Other events belong to one participant and can occur once for each participant.
These events are report handling, fix readiness, deployment, and embargo consent.
[What a Case Records](./what_a_case_records.md) describes these two kinds of event, the ledger that stamps each event, and the gaps in the ledger.

---

## Ordering is the sign of an interval

[Open Questions](./open_questions.md#what-timing-should-a-case-meet) names the gap this page addresses: the Case State (CS) model has a sense of order and no sense of time.
The measures of the [Foundations](foundations/index.md) count only whether each desideratum held in a case.
Consider two cases where fix readiness occurs before public awareness ($\mathbf{F} \prec \mathbf{P}$).
In one case, defenders had a month of warning, and in the other case, one minute.
The measures of the Foundations give the two cases the same score.

Every desideratum has a matching interval.
Let $\sigma_1$ and $\sigma_2$ be the two events of a desideratum $\sigma_1 \prec \sigma_2$.
Let $t(\sigma)$ be the time at which an event $\sigma$ occurred.
The **margin** of the desideratum is

$$m(\sigma_1 \prec \sigma_2) = t(\sigma_2) - t(\sigma_1)$$

A positive margin means the desideratum held, and its size says by how much.
A negative margin means it failed, and its size says how badly.
The measures of the Foundations keep only the sign of the margin $m$.
Thus each timing metric below adds detail to a Foundations measure, and does not replace it.

---

## Which clock to use

The [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) writes one case ledger entry for each change that it admits to the case.
Thus the ledger is a history of the case in time order, and almost every metric on this page uses the ledger as its data.

Each ledger entry carries two times: the commit stamp of the CASE_MANAGER, and the claimed time of the sender.
[What a Case Records](./what_a_case_records.md#two-clocks) describes the two times.
Every interval on this page uses the commit stamp by default, because all commit stamps in a case come from one clock.
The claimed time is useful only for the delay between an event and its commit, and only for the events of one participant.
The difference between the two clocks on one entry is itself a measure, listed under process health below.

---

## Kinds of measure

Five shapes cover the proposed metrics.

| Shape | Definition | Example |
|---|---|---|
| Interval | Time from one event to another | Time from awareness of vendor $i$ ($\mathbf{V}_i$) to fix readiness of vendor $i$ ($\mathbf{F}_i$) |
| Margin | A signed interval for an ordering desideratum | The margin of fix readiness before public awareness ($m(\mathbf{F} \prec \mathbf{P})$) |
| Dwell time | Total time the case spends in a state | Time with an embargo revision open |
| Spread | Time between the first and the last participant to reach the same event | Fix readiness of the first vendor ($\mathbf{F}$) to fix readiness of the last vendor ($\mathbf{F}$) |
| Count or rate | How often something happens in one case | Embargo Invites that end in a pocket veto |

---

## Intake and triage

These intervals measure how fast a report becomes a case and a commitment.

!!! note "Invitees and their two Invites"

    An Invitee is a participant that the case invites to join.
    The case first sends the Invitee a Stub Invite, which asks the Invitee to join and carries only a summary of the case.
    After the Invitee joins, the case sends a Full-Case Invite, which carries the full case and asks the Invitee to judge the report (CM-11-011).
    The [Glossary](../../reference/glossary.md#messaging-and-protocol) defines both Invites.
They are per-participant, because Report Management (RM) is per-participant.

| Metric | Definition |
|---|---|
| Time to validate | Report receipt by participant $i$ ($\mathbf{R}_i$) to report validation by participant $i$ ($\mathbf{Va}_i$) |
| Time to accept | Report validation by participant $i$ ($\mathbf{Va}_i$) to report acceptance by participant $i$ ($\mathbf{Ac}_i$) |
| Time to join, for an Invitee | Its Stub Invite to joining by participant $i$ ($\mathbf{J}_i$) |
| Time to judge, for an Invitee | Its Full-Case Invite to its answer, which is report validation by participant $i$ ($\mathbf{Va}_i$) when it accepts (CM-11-011) |

For an Invitee $i$, report receipt ($\mathbf{R}_i$) and joining ($\mathbf{J}_i$) are the same event.
The reason is that acceptance of the Stub Invite puts the Invitee at RM Received (CM-11-001).
For an Invitee, then, time to validate is time to judge plus the wait between joining and receiving the Full-Case Invite.
The case owner's report receipt ($\mathbf{R}$) and the reporter's report acceptance ($\mathbf{Ac}$) are set when the case is created.
Thus neither event has a measurable time ([What a Case Records](./what_a_case_records.md#statuses-seated-at-case-creation)).

---

## Embargo

These metrics describe how an embargo is negotiated, how long it lasts, and how it ends.
Embargo Management (EM) is per-case, and Participant Embargo Consent (PEC) is per participant and per embargo.

!!! note "Embargo terms used in this table"

    | Term | Meaning |
    |---|---|
    | Proposal | A participant proposes an embargo, and the case owner accepts or rejects the proposal |
    | Revision, EM Revise | A proposal to change the active embargo; the EM state is Revise while a revision is open |
    | RSVP deadline | The time by which an invited participant must answer an embargo Invite |
    | Pocket veto | An embargo Invite that reaches its RSVP deadline without an answer, so the consent row moves to `TIMED_OUT` |
    | Lapse | A participant lapses when it agreed to an earlier embargo, but has not agreed to the revision that is now active |
    | Threat signal | Public awareness, a public exploit, or observed attacks, each of which ends an active embargo early |

    The [Glossary](../../reference/glossary.md#embargo-and-timing) defines each term.

| Metric | Definition |
|---|---|
| Time to embargo | Case creation to the embargo start ($\mathbf{E}$), usually zero because a case starts with an active embargo |
| Decision latency | A proposal to the case owner's decision on it |
| Revision count and time in Revise | How many revisions were proposed, and the dwell time in EM Revise |
| Planned and actual length | The embargo's end time minus the time of the embargo start ($t(\mathbf{E})$), against the time of the embargo exit ($t(\mathbf{E_x})$) minus the time of the embargo start ($t(\mathbf{E})$) |
| Time left at exit | The embargo's end time minus the time of the embargo exit ($t(\mathbf{E_x})$); zero when the end time was reached |
| Exit cause | Whether the end time was reached, or the embargo ended early, and for an early end its recorded cause |
| Response latency | Each participant's time from an embargo Invite to its answer |
| Pocket-veto rate | The share of embargo Invites that move to `TIMED_OUT` at their RSVP deadline, not counting Invites that time out because the case owner closes the case |
| Lapse count | How many participants lapsed when a revision with longer terms came into force |

Time left at exit and exit cause together separate the two ways an embargo ends.
An embargo that ends early because every fix is ready ends on its own terms.
An embargo that ends early because of a threat signal has a margin of about zero against that threat signal.
With commit stamps, this margin is slightly negative, because the CASE_MANAGER commits the termination after the status that reported the threat signal.
The time left at exit of such an embargo is the cost of the threat.

---

## Fix and deployment

| Metric | Definition |
|---|---|
| Time to fix | Awareness of vendor $i$ ($\mathbf{V}_i$) to fix readiness of vendor $i$ ($\mathbf{F}_i$), per vendor |
| Time to deploy | Fix readiness of the first vendor ($\mathbf{F}$) to fix deployment by deployer $k$ ($\mathbf{D}_k$), per deployer |
| Notification spread | Awareness of the first vendor ($\mathbf{V}$) to awareness of the last vendor ($\mathbf{V}$) |
| Fix spread | Fix readiness of the first vendor ($\mathbf{F}$) to fix readiness of the last vendor ($\mathbf{F}$) |
| Trailing-vendor gap | Fix readiness of the last vendor ($\mathbf{F}$) to the embargo exit ($\mathbf{E_x}$); negative when the embargo ended before every fix was ready |

Time to deploy starts at the first fix readiness ($\mathbf{F}$) of any vendor in the case.
The reason is the protocol rule for deployment (CSB-15-004).
A deployer that is not also a vendor can move to fix deployment ($\mathbf{D}$) after any vendor has a fix ready.
The case does not record which vendor made the fix that a deployer deployed.
Thus the case cannot give a time to deploy for each vendor.

The spreads are Multi-Party CVD (MPCVD) measures.
The Foundations model has one vendor, so it has no spreads.
[Benchmarking MPCVD](./benchmarking_mpcvd.md) combines the outcomes of all vendors into one score, but does not decide how to combine them.
The fix spread and the trailing-vendor gap show the cost of the slowest vendor directly.
The fix spread shows how long the slowest vendor holds the case, and the trailing-vendor gap shows whether the embargo waited for the slowest vendor.

---

## Disclosure margins

Each desideratum gives a margin.
These are the margins most directly tied to defender outcomes.

| Margin | What a positive value measures |
|---|---|
| The margin of fix readiness before public awareness ($m(\mathbf{F} \prec \mathbf{P})$) | Lead time between a fix being ready and the vul being public |
| The margin of fix deployment before public awareness ($m(\mathbf{D} \prec \mathbf{P})$) | Lead time between deployment and the vul being public |
| The margin of the embargo exit before a participant publication ($m(\mathbf{E_x} \prec \mathbf{P_u})$) | Time a participant waited after the embargo before publishing |
| The margin of public awareness before a public exploit ($m(\mathbf{P} \prec \mathbf{X})$) | Time between the vul being public and an exploit being public |
| The margin of a public exploit before observed attacks ($m(\mathbf{X} \prec \mathbf{A})$) | Time between a public exploit and observed attacks |

---

## Exposure

Some states are bad to be in, and the time spent in them matters more than the order of their entry.
Exposure metrics are dwell times in those states.

| Metric | Definition |
|---|---|
| Public exposure | Time during which public awareness ($\mathbf{P}$) holds and fix deployment ($\mathbf{D}$) does not, per deployer |
| Exploit exposure | Time during which a public exploit ($\mathbf{X}$) holds and fix deployment ($\mathbf{D}$) does not, per deployer |
| Unfixed exposure | Time during which public awareness ($\mathbf{P}$) holds and fix readiness ($\mathbf{F}$) does not, per vendor |

[Open Questions](./open_questions.md#what-timing-should-a-case-meet) proposes a test of the vulnerability management of a deployer.
The test compares two intervals that start at fix readiness ($\mathbf{F}$).
The interval to fix deployment ($\mathbf{D}$) should be shorter than the interval to observed attacks ($\mathbf{A}$).
Exploit exposure measures a related race as a duration: the time during which an exploit is public and the deployer has not deployed the fix.

---

## Closure and case administration

| Metric | Definition |
|---|---|
| Case duration | Case creation to the case being fully closed |
| Time open after disclosure | Public awareness ($\mathbf{P}$) to the case being fully closed |
| Embargo Invites timed out at close | Embargo Invites still awaiting a reply that the owner's close moves to `TIMED_OUT` (CM-23-014) |
| Ownership transfer latency | An offer to transfer case ownership to its acceptance, rejection, withdrawal, or expiry |

A case is fully closed when the case owner leaves the case and the CASE_MANAGER closes its own report (CM-23-002).

---

## Process health

These metrics describe the protocol's own operation in a case, not the CVD outcome.
They help separate a slow case from a case whose messages went missing.

| Metric | Definition |
|---|---|
| Gap rate | RM status updates from participants that skip a step, which the CASE_MANAGER accepts and notes on the case (RSH-06-004) |
| Regression count | RM status updates from participants that move backward, which the CASE_MANAGER refuses and notes (RSH-06-002) |
| Refusal count | Assertions the CASE_MANAGER refused rather than admitted |
| Replay count | Requests from participants to send missed ledger entries again, because their replica fell behind |
| Clock skew | Commit stamp minus claimed time, per participant |

A gap is a forward move that skips a step the CASE_MANAGER never saw.
Either a message was lost, or the participant took the step locally and reported only its latest state.
A rising gap rate is therefore a prompt to look for lost messages, not proof of them.
A large clock skew for one participant means its claimed times cannot be trusted for intervals.

---

## Gaps in the data

Most of the metrics above can be computed from the case ledger as it is.
Some metrics are not exact, because the ledger stamps some events late, stamps some events with the creation time, or does not record some events.
[What a Case Records](./what_a_case_records.md#data-gaps) lists these data gaps.
A metric that uses an event with a data gap has the same gap.

---

## Intervals to events that have not happened

Many cases never see a public exploit ($\mathbf{X}$) or observed attacks ($\mathbf{A}$), and an open case has not yet closed.
An interval that ends at an event that has not occurred is **censored**.
A censored interval is not missing: the interval is at least as long as the case has run.
Treating censored intervals as missing biases every average toward the cases that finished.
Across cases, censored intervals call for survival-analysis methods, such as a Kaplan–Meier estimate of time to fix, and medians rather than means.

---

## Relation to service level expectations

[Open Questions](./open_questions.md#what-timing-should-a-case-meet) and [Policy Formalization](../other_uses/policy_formalization.md) describe Service Level Expectations (SLEs).
An SLE is a timer that starts and stops on transitions, such as a limit on the time from vendor awareness ($\mathbf{V}$) to fix readiness ($\mathbf{F}$).
An SLE is a threshold on one of the intervals above.
Defining the intervals first lets an SLE be stated as a number against a metric that already has a definition.
It also lets a program report the distribution of an interval across its cases, rather than only how often it met a threshold.

---

## In a two-party case

A two-party case has one reporter and one vendor.
A two-party case is a special case of the same model, not a different model.
The table below shows how each group of metrics changes in a two-party case.

| Metrics | In a two-party case |
|---|---|
| Intake and triage for the vendor, all embargo metrics, time to fix, closure, process health | No change |
| Disclosure margins without fix deployment ($\mathbf{D}$) | No change |
| Notification spread, fix spread | Always zero, because the case has one vendor |
| Trailing-vendor gap | The interval from the fix readiness ($\mathbf{F}$) of the one vendor to the embargo exit ($\mathbf{E_x}$) |
| Time to deploy, margins with fix deployment ($\mathbf{D}$), public exposure, exploit exposure | Not available, unless the vendor also has the Deployer role |

The deployment metrics need a participant with a deployment state.
A vendor has a deployment state only when the vendor also has the Deployer role (SDO-03-002).

---

## Summary

| Area | Representative metrics |
|---|---|
| Intake and triage | Time to validate, accept, judge, join |
| Embargo | Decision latency, revisions, planned and actual length, time left at exit, exit cause, response latency, pocket-veto rate |
| Fix and deployment | Time to fix and deploy; notification spread, fix spread, trailing-vendor gap |
| Disclosure margins | The margin of fix readiness before public awareness ($m(\mathbf{F} \prec \mathbf{P})$), the margin of fix deployment before public awareness ($m(\mathbf{D} \prec \mathbf{P})$), the margin of public awareness before a public exploit ($m(\mathbf{P} \prec \mathbf{X})$), and the margin of every other desideratum |
| Exposure | Time with public awareness ($\mathbf{P}$) or a public exploit ($\mathbf{X}$) and no fix deployment ($\mathbf{D}$) |
| Closure | Case duration, time open after disclosure, embargo Invites timed out at close, transfer latency |
| Process health | Gap rate, regressions, refusals, replays, clock skew |

## Further reading

- [Desiderata from the Process Models](./process_model_desiderata.md) — the extended events and orderings whose margins this page measures.
- [Desirable Histories](./desirable_histories.md) — the original twelve desiderata.
- [What a Case Records](./what_a_case_records.md) — the per-case and per-participant state, the two clocks, and the data gaps.
- [Open Questions](./open_questions.md) — the difference between order and time, and the first proposal for service level expectations.
- [The CASE_MANAGER and the Case Ledger](../case_lifecycle/case_manager_and_ledger.md) — the ledger that supplies every timestamp.
