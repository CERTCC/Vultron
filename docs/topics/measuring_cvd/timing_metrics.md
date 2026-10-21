---
stakeholder_type: [process-researcher]
level: 500
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
It uses the notation of that page: $\mathbf{V}_i$, $\mathbf{F}_i$, and $\mathbf{D}_i$ for vendor $i$'s awareness, fix readiness, and deployment; $\mathbf{P}$, $\mathbf{X}$, and $\mathbf{A}$ for public awareness, a public exploit, and observed attacks; $\mathbf{E}$ and $\mathbf{E_x}$ for an embargo coming into force and ending.

---

## Ordering is the sign of an interval

[CS Model Limitations](../process_models/cs/cs_model_limitations.md) names the gap this page addresses: the Case State (CS) model has a sense of order and no sense of time.
Two cases can both satisfy $\mathbf{F} \prec \mathbf{P}$, one with a month of warning for defenders and one with a minute.
The ordering measure scores them the same.

Every ordering desideratum $\sigma_1 \prec \sigma_2$ has a matching interval.
Write $t(\sigma)$ for the time event $\sigma$ occurred, and define the **margin** of the desideratum as

$$m(\sigma_1 \prec \sigma_2) = t(\sigma_2) - t(\sigma_1)$$

A positive margin means the desideratum held, and its size says by how much.
A negative margin means it failed, and its size says how badly.
The ordering measure keeps only the sign of $m$, so every timing metric below refines an ordering measure rather than replacing it.

---

## What the ledger records

The [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) writes one case ledger entry for each admitted change to the case.
Every report-management status, embargo step, consent change, participant status, and case status is its own entry.
The ledger is therefore a time-ordered history of the case, and it is the data source for every metric on this page.

Each entry carries two kinds of order and two clocks.

| Field | Meaning | Use for metrics |
|---|---|---|
| Log index | The entry's position in the hash chain | The authoritative causal order (CLP-14-001) |
| Commit stamp | The CASE_MANAGER's own clock at commit time (CLP-14-002, CM-02-009) | One clock for the whole case; the default for intervals |
| Claimed time | The time the asserting participant put on its activity | Each participant's own clock, monotonic only within that participant's stream (CLP-15-003) |

The commit stamp is the safer default.
It comes from one clock, so intervals between any two entries are comparable.
It records when the CASE_MANAGER learned of an event, which can be later than when the event happened.
The claimed time is closer to the event, but two participants' clocks can disagree.
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
| Count or rate | How often something happens in one case | Embargo invitations that time out |

---

## Intake and triage

These intervals measure how fast a report becomes a case and a commitment.
They are per-participant, because Report Management (RM) is per-participant.

| Metric | Definition |
|---|---|
| Time to validate | $\mathbf{R}_i$ to $\mathbf{Va}_i$ |
| Time to accept | $\mathbf{Va}_i$ to $\mathbf{Ac}_i$ |
| Time to judge, for an invitee | Invitation to the participant's answer to the full-case invitation |
| Time to join | Invitation to $\mathbf{J}_i$ |

The first two intervals are not measurable for the case owner from commit stamps; the [data gaps](#data-gaps) section explains why.

---

## Embargo

These metrics describe how an embargo is negotiated, how long it lasts, and how it ends.
Embargo Management (EM) is per-case, and Participant Embargo Consent (PEC) is per participant and per embargo.

| Metric | Definition |
|---|---|
| Time to embargo | Case creation to $\mathbf{E}$, usually zero because a case starts with an embargo in force |
| Decision latency | A proposal to the case owner's decision on it |
| Revision count and time in Revise | How many revisions were proposed, and the dwell time in EM Revise |
| Planned and actual length | The embargo's end time minus $t(\mathbf{E})$, against $t(\mathbf{E_x})$ minus $t(\mathbf{E})$ |
| Time left at exit | The embargo's end time minus $t(\mathbf{E_x})$; zero when the end time was reached |
| Exit cause | Whether the end time was reached, or the embargo ended early, and for an early end its recorded cause |
| Response latency | Each participant's time from embargo invitation to its answer |
| Time-out rate | The share of embargo invitations that time out unanswered |
| Lapse count | How many participants lapsed when a revision with longer terms came into force |

Time left at exit and exit cause together separate the two ways an embargo ends.
An embargo that ends early because every fix is ready ends on its own terms.
An embargo that ends early because of a threat signal has a margin of zero against $\mathbf{P}$, $\mathbf{X}$, or $\mathbf{A}$, and its time left at exit is what the threat cost.

---

## Fix and deployment

| Metric | Definition |
|---|---|
| Time to fix | $\mathbf{V}_i$ to $\mathbf{F}_i$, per vendor |
| Time to deploy | $\mathbf{F}_i$ to $\mathbf{D}_k$, per vendor and deployer |
| Notification spread | First vendor's $\mathbf{V}$ to last vendor's $\mathbf{V}$ |
| Fix spread | First vendor's $\mathbf{F}$ to last vendor's $\mathbf{F}$ |
| Trailing-vendor gap | Last vendor's $\mathbf{F}$ to $\mathbf{E_x}$; negative when the embargo ended before every fix was ready |

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

CS Model Limitations proposes that a vulnerability management process is effective when the lag from $\mathbf{F}$ to $\mathbf{D}$ is shorter than the lag from $\mathbf{F}$ to $\mathbf{A}$.
Exploit exposure measures the same race as a duration.

---

## Closure and case administration

| Metric | Definition |
|---|---|
| Case duration | Case creation to the case being fully closed |
| Time open after disclosure | $\mathbf{P}$ to the case being fully closed |
| Invitations expired at close | Pending invitations that the owner's close times out |
| Ownership transfer latency | An offer to transfer case ownership to its acceptance, rejection, withdrawal, or expiry |

---

## Process health

These metrics describe the protocol's own operation in a case, not the CVD outcome.
They help separate a slow case from a case whose messages went missing.

| Metric | Definition |
|---|---|
| Gap rate | Received RM declarations that skip a step, which the receiver accepts but flags as a gap |
| Refusal count | Assertions the CASE_MANAGER refused rather than admitted |
| Replay count | Ledger replays requested by participants whose replica fell behind |
| Clock skew | Commit stamp minus claimed time, per participant |

A rising gap rate suggests lost messages, because a gap is a forward move whose intermediate step never arrived.
A large clock skew for one participant means its claimed times cannot be trusted for intervals.

---

## Data gaps

Most of the metrics above can be computed from the case ledger as it is.
Four gaps limit them.

### Intake before the case exists

A report is received, validated, and accepted by its first recipient before the case is created.
The statuses seated at case creation are committed in the creation sequence, so their commit stamps carry the creation time, not the time each decision was made.
The first recipient's time to validate and time to accept are therefore not recoverable from commit stamps.
The report's own received time lives with the recipient, outside the case ledger.

### Commit time is not occurrence time

A commit stamp records when the CASE_MANAGER learned of an event.
For protocol acts, such as an acceptance, an embargo step, or a join, the two are close.
For $\mathbf{X}$ and $\mathbf{A}$, which happen outside the protocol, the lag between occurrence and the participant's report of it can be long and is not measured.
[CS Model Limitations](../process_models/cs/cs_model_limitations.md) discusses the observability of these events; it applies to their times as much as to their order.

### Embargo records carry no times of their own

An entry in the embargo register and a participant's consent row hold a status and no timestamp.
Their timing comes only from the ledger entries that recorded each step.
Every embargo metric therefore needs a join from the register and the consent rows back to the ledger.

### Intervals to events that have not happened

Many cases never see $\mathbf{X}$ or $\mathbf{A}$, and an open case has not yet closed.
An interval that ends at an event that has not happened is **censored**: it is known to be at least as long as the case has run, not missing.
Treating censored intervals as missing biases every average toward the cases that finished.
Across cases, censored intervals call for survival-analysis methods, such as a Kaplan–Meier estimate of time to fix, and medians rather than means.

---

## Relation to service level expectations

[CS Model Limitations](../process_models/cs/cs_model_limitations.md) and [Policy Formalization](../other_uses/policy_formalization.md) sketch Service Level Expectations (SLEs): timers that start and stop on transitions, such as a bound on the time from $\mathbf{V}$ to $\mathbf{F}$.
An SLE is a threshold on one of the intervals above.
Defining the intervals first lets an SLE be stated as a number against a metric that already has a definition.
It also lets a program report the distribution of an interval across its cases, rather than only how often it met a threshold.

---

## Summary

| Area | Representative metrics |
|---|---|
| Intake and triage | Time to validate, accept, judge, join |
| Embargo | Decision latency, revisions, planned and actual length, time left at exit, exit cause, response latency, time-out rate |
| Fix and deployment | Time to fix and deploy; notification spread, fix spread, trailing-vendor gap |
| Disclosure margins | $m(\mathbf{F} \prec \mathbf{P})$, $m(\mathbf{D} \prec \mathbf{P})$, $m(\mathbf{P} \prec \mathbf{X})$, and the margin of every other desideratum |
| Exposure | Time with $\mathbf{P}$ or $\mathbf{X}$ and no $\mathbf{D}$ |
| Closure | Case duration, time open after disclosure, invitations expired, transfer latency |
| Process health | Gap rate, refusals, replays, clock skew |

## Further reading

- [Desiderata from the Process Models](./process_model_desiderata.md) — the extended events and orderings whose margins this page measures.
- [Desirable Histories](./desirable_histories.md) — the original twelve desiderata.
- [CS Model Limitations](../process_models/cs/cs_model_limitations.md) — the ordering-versus-timing limitation and the first sketch of service level expectations.
- [The CASE_MANAGER and the Case Ledger](../case_lifecycle/case_manager_and_ledger.md) — the ledger that supplies every timestamp.
