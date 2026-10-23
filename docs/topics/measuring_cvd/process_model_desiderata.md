---
stakeholder_type: [process-researcher]
level: 500
page_type: explanation
description: >
  Ordering preferences beyond the original twelve, distilled from the report, embargo, consent, and multi-party process models.
---

# Desiderata from the Process Models

{% include-markdown "../../includes/not_normative.md" %}

This page proposes desired event orderings that go beyond the twelve in [Desirable Histories](./desirable_histories.md).
The twelve come from the six-event Case State (CS) model of the original research.
The protocol has since modeled Report Management (RM), Embargo Management (EM), Participant Embargo Consent (PEC), and multi-party participation in much more detail.
Those models imply further preferences about what should happen before what.
The page is a draft research proposal for people who study the Coordinated Vulnerability Disclosure (CVD) process; none of it is normative, and its candidates have not been validated against case data.

The page assumes the set of desiderata $\mathbb{D}$ and the notation $\sigma_1 \prec \sigma_2$ from [Desirable Histories](./desirable_histories.md).
It assumes the skill coefficient $\alpha_d$ from [Discriminating Skill and Luck](./discriminating_skill_and_luck.md), and the per-vendor case state of Multi-Party CVD (MPCVD) from [Benchmarking MPCVD](./benchmarking_mpcvd.md).
The process models it draws on are [RM](../process_models/rm/index.md), [EM](../process_models/em/index.md), and their [interactions with CS](../process_models/model_interactions/index.md).

Each desideratum relates events of two kinds.
Some events belong to the case and happen once in it: public awareness, a public exploit, observed attacks, and the embargo's start and end.
Others belong to one participant and can happen once for each: its report handling, its fix or deployment, its joining, and its consent to an embargo.
[What a Case Records](./what_a_case_records.md) sets out that split and how the case ledger records each event.

---

## A desideratum is useful only if a case can fail it

A desideratum is useful as a measure of skill only if a case can fail it.
The skill coefficient compares how often an ordering holds with how often it would hold by chance.
An ordering that the protocol enforces holds in every conforming case, so its observed frequency is 1 and its $\alpha_d$ says nothing about skill.

The process models contain both kinds of rule.
A MUST that the implementation enforces is a **conformance ordering**: a history that breaks it is a broken implementation, not an unskilled case.
A SHOULD, or a preference the models state without a requirement, can be broken by a conforming case, and is a candidate desideratum.
The candidates below come from the second kind.
The first kind is listed at the end of the page, because it is still worth checking.

---

## Events beyond the six

The six CS events are vendor awareness $\mathbf{V}$, fix ready $\mathbf{F}$, fix deployed $\mathbf{D}$, public awareness $\mathbf{P}$, exploit public $\mathbf{X}$, and attacks observed $\mathbf{A}$.
The process models add the following events.
Each is recorded by the [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) as an entry in the case ledger, though the statuses seated when the case is created carry the creation time, not the time of the decision ([What a Case Records](./what_a_case_records.md#statuses-seated-at-case-creation)).

| Event | Meaning | Process model |
|---|---|---|
| $\mathbf{R}_i$ | Participant $i$ receives the report | RM Start → Received |
| $\mathbf{Va}_i$ | Participant $i$ validates the report | RM → Valid |
| $\mathbf{Ac}_i$ | Participant $i$ accepts the report for work | RM → Accepted |
| $\mathbf{C}_i$ | Participant $i$ closes the report | RM → Closed |
| $\mathbf{E}$ | An embargo first comes into force on the case | EM → Active |
| $\mathbf{E_x}$ | The embargo ends | EM → eXited |
| $\mathbf{J}_i$ | Participant $i$ joins the case | Accepting its Stub Invite (CM-11-001) |
| $\mathbf{S}_i$ | Participant $i$ agrees to the active embargo | PEC → `AGREED` |

The subscript $i$ marks a per-participant event.
The original six already mix scopes: $\mathbf{V}$ and $\mathbf{F}$ are per vendor, $\mathbf{D}$ is per deployer, and $\mathbf{P}$, $\mathbf{X}$, and $\mathbf{A}$ belong to the whole case.
This page writes $\mathbf{V}_i$ and $\mathbf{F}_i$ for vendor $i$ and $\mathbf{D}_k$ for deployer $k$.
$\mathbf{E}$ and $\mathbf{E_x}$ also belong to the whole case, because a case has at most one active embargo.
Under an active embargo, $\mathbf{J}_i$ and $\mathbf{S}_i$ are one event: accepting the Stub Invite both joins the case and agrees to the embargo (CM-11-001).
They separate only for a participant that joins with no active embargo, or that answers a later embargo.

### Splitting events by cause

Two events need to be split by what caused them, because the same state change can be a success or a failure.

| Split | Meaning |
|---|---|
| $\mathbf{E_x^\ast}$ | The embargo ends on its own terms: its end time is reached, or it ends early because fixes are ready or deployed |
| $\mathbf{E_x^!}$ | The embargo ends because of a threat signal: public awareness, a public exploit, or observed attacks |
| $\mathbf{P_u}$ | Public awareness comes from a participant's coordinated publication |
| $\mathbf{P_\ell}$ | Public awareness comes from outside the case, such as a leak or an independent disclosure |

The protocol records most of the first split.
A terminated embargo carries what ended it, `END_TIME_REACHED` or `EARLY`, and, when known, a structured cause of `THREAT_SIGNAL`, `FIX_READY`, `FIX_DEPLOYED`, or `OTHER` (EMB-13-004).
`END_TIME_REACHED`, `FIX_READY`, and `FIX_DEPLOYED` are $\mathbf{E_x^\ast}$, and `THREAT_SIGNAL` is $\mathbf{E_x^!}$.
An early end with the cause `OTHER`, or with no cause recorded, is neither, and a measure has to either set it aside or classify it from the case's other events.
The second split is not recorded as such.
A publication by a participant is a protocol action, so it can be told apart from a $\mathbf{P}$ that arrives from outside, but nothing labels the case's $\mathbf{P}$ with its source.

---

## Embargo desiderata

An embargo is a means, not an end.
It exists to give vendors time to make $\mathbf{F}$ and $\mathbf{D}$ precede $\mathbf{P}$, $\mathbf{X}$, and $\mathbf{A}$.
The embargo desiderata therefore rank below the fix desiderata of $\mathbb{D}$, and a case that achieves $\mathbf{F} \prec \mathbf{P}$ without an embargo is not a worse case.

| Ordering preference | Meaning | Source |
|---|---|---|
| $\mathbf{E} \prec \mathbf{P}$, $\mathbf{E} \prec \mathbf{X}$, $\mathbf{E} \prec \mathbf{A}$ | An embargo is active before the vul is public, exploited, or attacked | A case starts in EM Active at creation, under a published default or the protocol default ([Default Embargoes](../process_models/em/defaults.md)) |
| $\mathbf{E_x^\ast} \prec \mathbf{P}$, $\mathbf{E_x^\ast} \prec \mathbf{X}$, $\mathbf{E_x^\ast} \prec \mathbf{A}$ | The embargo ends on its own terms, not because a threat signal ended it | An embargo ends early at $\mathbf{P}$, $\mathbf{X}$, or $\mathbf{A}$ ([CVD Case State Interactions with the RM and EM Process Models](../process_models/model_interactions/rm_em_cs.md)) |
| $\mathbf{E_x} \prec \mathbf{P_u}$ | Participants publish only after the embargo ends | VP-05-006, VP-05-014 |
| $\mathbf{E_x} \prec \mathbf{X}$ for an exploit a participant publishes | Exploit publishers wait for the embargo to end | VP-14-012 |
| $\mathbf{F}_i \prec \mathbf{E_x^\ast}$ for every vendor $i$ | Every vendor's fix is ready before the embargo ends | VP-14-009 asks participants to extend for trailing vendors; VP-09-007 permits ending at a quorum |
| $\mathbf{E_x} \prec \mathbf{C}_i$ | A participant does not close its report while an embargo is active or under revision, unless it first tells the others it is closing and what its embargo stance is | RMB-14-003 |

The first row is close to a conformance ordering.
A case is created in EM Active unless $\mathbf{P}$, $\mathbf{X}$, or $\mathbf{A}$ already holds, in which case it stays in EM None (EP-04-005, EP-04-008).
So $\mathbf{E} \prec \mathbf{P}$ fails only when the report arrives, or the case is created, after the vul is already public, and it measures when the case formed more than how it was run.

The second row is the sharpest of these.
Any $\mathbf{E_x}$ that follows $\mathbf{P}$ or $\mathbf{X}$ is an $\mathbf{E_x^!}$, because public awareness or a public exploit ends an active embargo (VP-09-001).
Observed attacks SHOULD end it too (VP-09-003), so an $\mathbf{E_x}$ after $\mathbf{A}$ is usually, but not always, an $\mathbf{E_x^!}$.
So $\mathbf{E_x^\ast} \prec \mathbf{P}$ says that the case reached the end of its embargo before the race with disclosure was lost.

The fifth row is stronger than the protocol requires.
VP-09-007 lets an embargo end when a quorum of vendors is ready, even if some are not.
The desideratum names the ideal, every vendor ready; the quorum is what the protocol tolerates.
A case that ends at a quorum fails the desideratum for each trailing vendor, which is the outcome the measure should count.

---

## Report-handling desiderata

$\mathbb{D}$ treats vendor awareness as the first good event.
The RM model separates awareness from engagement: a vendor can know of a report and still not validate it, accept it, or work on it.

| Ordering preference | Meaning | Source |
|---|---|---|
| $\mathbf{Ac}_i \prec \mathbf{P}$, $\mathbf{Ac}_i \prec \mathbf{X}$, $\mathbf{Ac}_i \prec \mathbf{A}$ for every affected vendor $i$ | The vendor has committed to work on the report before the vul is public, exploited, or attacked | [Reward Functions](./reward_functions.md) prefers RM paths that pass through Accepted |
| $\mathbf{Va}_i \prec \mathbf{P}$ for every affected vendor $i$ | The vendor has judged the report valid before the vul is public | Validation is the first RM decision |
| $\mathbf{Ac}_i \prec \mathbf{F}_i$ for every vendor $i$ | The vendor accepts the report before its fix is ready, rather than deferring or closing it first | CSB-18-001 also permits a fix from Deferred or Closed |

$\mathbf{Ac}_i \prec \mathbf{P}$ implies $\mathbf{V}_i \prec \mathbf{P}$, because a vendor cannot accept a report it has not received.
It is the stronger claim: it rewards a vendor that engages, not one that only knows.
It also covers the gap between $\mathbf{V}$ and $\mathbf{F}$, where $\mathbb{D}$ has nothing to say.

$\mathbf{Ac}_i \prec \mathbf{F}_i$ is only partly enforced.
Fix readiness can be asserted only once the vendor's RM state is Accepted, Deferred, or Closed (CSB-18-001), and RM reaches Deferred from Valid and Closed from Received without passing through Accepted.
A vendor that defers a report and then ships a fix anyway satisfies the protocol and fails the desideratum, which is the case the measure should count.

---

## Multi-party desiderata

[Benchmarking MPCVD](./benchmarking_mpcvd.md) applies $\mathbb{D}$ to each vendor separately and then aggregates.
The orderings below relate one participant's events to another's, so a per-vendor history cannot express them.

| Ordering preference | Meaning | Source |
|---|---|---|
| $\mathbf{V}_i \prec \mathbf{F}_j$ for all affected vendors $i, j$ | Every affected vendor learns of the vul before any vendor's fix is ready | Keeps the trailing vendor's time to fix from starting late |
| $\mathbf{J}_k \prec \mathbf{F}_i$ for every deployer $k$ and every vendor $i$ | A deployer is in the case before any vendor's fix is ready | Without it, $\mathbf{D}_k \prec \mathbf{P}$ is out of reach for a deployer that is not also a vendor |
| $\mathbf{S}_k \prec$ the first case content sent to $k$ | A participant agrees to the embargo before it receives the case | VP-08-006, EMB-11-001 |
| $\mathbf{F}_i \prec \mathbf{P}$ for every vendor $i$ | Every vendor's fix is ready before the vul is public | $\mathbf{F} \prec \mathbf{P}$ from $\mathbb{D}$, quantified over vendors |

The deployer row deserves attention.
It is stated against every vendor because the case does not pair a deployer with a vendor.
A deployer that is not also a vendor may deploy once any vendor in the case has a fix ready (CSB-15-004), and the case records no link from a deployment to the fix it applied.
The protocol requires no deployer to be invited at all.
In the original single-vendor model, $\mathbf{D}$ is the vendor's deployment or an aggregate over its users.
In a multi-party case, a deployer that joins only after $\mathbf{P}$ cannot achieve $\mathbf{D} \prec \mathbf{P}$, however quickly it acts.

The consent row is partly enforced.
While an embargo is active, the CASE_MANAGER shares no case content with a participant that has not agreed to it: no case ledger entry, case announcement, status broadcast, or embargo announcement (CM-10-004, CM-10-005).
The SHOULDs in VP-08-006 and EMB-11-001 also cover sharing by other routes, which the protocol cannot see.
For case content the row is a conformance ordering, and for everything else it is a desideratum that can only be observed indirectly.

The last row makes one aggregation choice explicit.
Benchmarking MPCVD leaves open how per-vendor outcomes combine, and lists majority and risk-weighted rules as options.
"Every vendor" is the strictest rule, and it is the one the embargo desiderata above already assume.

---

## Preferences about the path

Some preferences are not orderings of two events.
They are about the shape of a history: how many steps it takes, or how a decision was reached.

| Preference | Process model |
|---|---|
| A participant answers an embargo Invite before its RSVP deadline, rather than leaving it to a pocket veto | PEC: `AGREED` or `DECLINED` over `TIMED_OUT`, not counting the Invites the case's close times out (CM-23-014) |
| A case revises its embargo few times | EM: few passes through Revise |
| An embargo is as short as the fixes allow | [EM Principles](../process_models/em/principles.md) |
| A report is judged correctly: a real vul is Valid and a bogus report is Invalid | RM: validation accuracy |

[Reward Functions](./reward_functions.md) already treats these as criteria for reward functions over RM and EM histories.
They are listed here for completeness, not as new proposals.
Ordering desiderata and path preferences need different measures: the first fits the frequency-based $\alpha_d$, and the second needs a score over the whole history.

---

## Conformance orderings

The orderings below are enforced by the protocol.
They are not desiderata, because a conforming case cannot fail them.
They are still worth checking against case data, because a history that breaks one shows a defect in an implementation.

| Ordering | Requirement |
|---|---|
| $\mathbf{V}_i \prec \mathbf{F}_i$ for every vendor $i$ | The vendor fix path ([History Constraints](./possible_histories.md)) |
| $\mathbf{F}_i \prec \mathbf{D}_k$ for some vendor $i$, for every deployer $k$ that is not also a vendor | CSB-15-004 |
| $\mathbf{F}_i$ only once participant $i$'s RM state is Accepted, Deferred, or Closed | CSB-18-001 |
| A report is never closed from Valid | VP-02-004, RMB-14-004 |
| The case is initialized before anyone else is invited and before any embargo change | CM-14-007 |
| An embargo end time is set before the case reaches RM Valid | DUR-07-004 |
| $\mathbf{S}_k \prec$ any case content sent to $k$, while an embargo is active | CM-10-004, CM-10-005 |

---

## Open problems

The candidates above are proposals.
Three problems stand between them and a measure like the one in [Discriminating Skill and Luck](./discriminating_skill_and_luck.md).

### The baseline needs a new walk

The skill coefficient needs the frequency $f_d$ with which each ordering holds by chance.
For $\mathbb{D}$, that frequency comes from a uniform [random walk](./random_walk.md) over the six-event CS model.
The new events live in a joint space of RM, EM, PEC, and CS states, so their baselines need a walk over that joint space.

The coupling rules between the models change the frequencies, and the change can be large.
Public awareness ends an active embargo, so $\mathbf{P}$ and $\mathbf{E_x^!}$ arrive together, and fix readiness requires an RM state of Accepted, Deferred, or Closed, so $\mathbf{F}$ can never precede the first of those.
A walk that ignores these couplings gives baselines for histories that cannot occur.
How large each $f_d$ is under the coupled walk has not been computed.

### The desiderata are not independent

$\mathbf{Ac}_i \prec \mathbf{P}$ implies $\mathbf{V}_i \prec \mathbf{P}$.
$\mathbf{F}_i \prec \mathbf{E_x^\ast}$ for every vendor, combined with $\mathbf{E_x^\ast} \prec \mathbf{P}$, implies $\mathbf{F}_i \prec \mathbf{P}$ for every vendor.
The skill score in [Reasoning Over Histories](./reasoning_over_histories.md) sums over desiderata, so correlated desiderata count the same skill more than once.
The extended set needs either a weighting or a smaller basis.

### The new events are more observable than the old

[What a Case Records](./what_a_case_records.md#who-observes-what) notes that $\mathbf{X}$ and $\mathbf{A}$ happen outside the protocol, and [Open Questions](./open_questions.md#when-is-a-fix-deployed) that $\mathbf{D}$ needs a threshold to be observed at all.
Most of the new events are protocol acts: the CASE_MANAGER writes $\mathbf{Ac}_i$, $\mathbf{E}$, $\mathbf{E_x}$, $\mathbf{J}_i$, and $\mathbf{S}_i$ to the case ledger when it admits them, except for the statuses seated at case creation, which carry the creation time.
A desideratum between two protocol acts can be measured from the ledger alone.
A desideratum that involves $\mathbf{X}$ or $\mathbf{A}$ inherits their observation problems, as the originals do.

---

## In a two-party case

A two-party case, with one reporter and one vendor, is the special case of the same model, not a separate one.
The embargo and report-handling desiderata carry over unchanged, with $i$ ranging over the one vendor.
Of the multi-party desiderata, $\mathbf{V}_i \prec \mathbf{F}_j$ collapses to $\mathbf{V} \prec \mathbf{F}$, which the vendor fix path already enforces, and "every vendor's fix" becomes the one vendor's fix.
The deployer row disappears unless some participant holds the deployer role.
The consent row holds trivially for the reporter, which the case seeds as a signatory of any active embargo when it is created (CM-14-012).

---

## Summary

| Group | Desiderata |
|---|---|
| Embargo | $\mathbf{E} \prec \mathbf{P}, \mathbf{X}, \mathbf{A}$; $\mathbf{E_x^\ast} \prec \mathbf{P}, \mathbf{X}, \mathbf{A}$; $\mathbf{E_x} \prec \mathbf{P_u}$; $\mathbf{E_x} \prec$ a participant's $\mathbf{X}$; $\mathbf{F}_i \prec \mathbf{E_x^\ast}$; $\mathbf{E_x} \prec \mathbf{C}_i$ |
| Report handling | $\mathbf{Ac}_i \prec \mathbf{P}, \mathbf{X}, \mathbf{A}$; $\mathbf{Va}_i \prec \mathbf{P}$; $\mathbf{Ac}_i \prec \mathbf{F}_i$ |
| Multi-party | $\mathbf{V}_i \prec \mathbf{F}_j$; $\mathbf{J}_k \prec \mathbf{F}_i$ for every deployer and vendor; $\mathbf{S}_k \prec$ first content to $k$; $\mathbf{F}_i \prec \mathbf{P}$ for every vendor |
| Path shape | Answered invitations, few revisions, short embargoes, accurate validation |

## Further reading

- [Desirable Histories](./desirable_histories.md) — the twelve original desiderata and the partial order they induce.
- [What a Case Records](./what_a_case_records.md) — how the case ledger records these events, and the gaps in what it records.
- [Timing Metrics Within a Case](./timing_metrics.md) — measuring the intervals between these events, not only their order.
- [Benchmarking MPCVD](./benchmarking_mpcvd.md) — per-vendor histories and how they might aggregate.
- [CVD Case State Interactions with the RM and EM Process Models](../process_models/model_interactions/rm_em_cs.md) — the couplings between the models that these desiderata draw on.
