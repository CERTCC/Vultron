---
stakeholder_type: [process-researcher]
level: 500
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
Each is recorded by the [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) as an entry in the case ledger.

| Event | Meaning | Process model |
|---|---|---|
| $\mathbf{R}_i$ | Participant $i$ receives the report | RM Start → Received |
| $\mathbf{Va}_i$ | Participant $i$ validates the report | RM → Valid |
| $\mathbf{Ac}_i$ | Participant $i$ accepts the report for work | RM → Accepted |
| $\mathbf{C}_i$ | Participant $i$ closes the report | RM → Closed |
| $\mathbf{E}$ | An embargo first comes into force on the case | EM → Active |
| $\mathbf{E_x}$ | The embargo ends | EM → eXited |
| $\mathbf{J}_i$ | Participant $i$ joins the case | Accepting its invitation to the case |
| $\mathbf{S}_i$ | Participant $i$ agrees to the embargo in force | PEC → `AGREED` |

The subscript $i$ marks a per-participant event.
The original six already mix scopes: $\mathbf{V}$, $\mathbf{F}$, and $\mathbf{D}$ are per-vendor, while $\mathbf{P}$, $\mathbf{X}$, and $\mathbf{A}$ belong to the whole case.
$\mathbf{E}$ and $\mathbf{E_x}$ also belong to the whole case, because a case has at most one embargo in force.

### Splitting events by cause

Two events need to be split by what caused them, because the same state change can be a success or a failure.

| Split | Meaning |
|---|---|
| $\mathbf{E_x^\ast}$ | The embargo ends on its own terms: its end time is reached, or a quorum of fixes is ready or deployed |
| $\mathbf{E_x^!}$ | The embargo ends because of a threat signal: public awareness, a public exploit, or observed attacks |
| $\mathbf{P_u}$ | Public awareness comes from a participant's coordinated publication |
| $\mathbf{P_\ell}$ | Public awareness comes from outside the case, such as a leak or an independent disclosure |

The protocol records the first split directly.
A terminated embargo carries what ended it, `END_TIME_REACHED` or `EARLY`, and for an early end a structured cause of `THREAT_SIGNAL`, `FIX_READY`, `FIX_DEPLOYED`, or `OTHER` (EMB-13-004).
The second split is not recorded as such.
A publication by a participant is a protocol action, so it can be told apart from a $\mathbf{P}$ that arrives from outside, but nothing labels the case's $\mathbf{P}$ with its source.

---

## Embargo desiderata

An embargo is a means, not an end.
It exists to give vendors time to make $\mathbf{F}$ and $\mathbf{D}$ precede $\mathbf{P}$, $\mathbf{X}$, and $\mathbf{A}$.
The embargo desiderata therefore rank below the fix desiderata of $\mathbb{D}$, and a case that achieves $\mathbf{F} \prec \mathbf{P}$ without an embargo is not a worse case.

| Ordering preference | Meaning | Source |
|---|---|---|
| $\mathbf{E} \prec \mathbf{P}$, $\mathbf{E} \prec \mathbf{X}$, $\mathbf{E} \prec \mathbf{A}$ | An embargo is in force before the vul is public, exploited, or attacked | A case starts in EM Active at creation, under a published default or the protocol default ([Default Embargoes](../process_models/em/defaults.md)) |
| $\mathbf{E_x^\ast} \prec \mathbf{P}$, $\mathbf{E_x^\ast} \prec \mathbf{X}$, $\mathbf{E_x^\ast} \prec \mathbf{A}$ | The embargo ends on its own terms, not because a threat signal ended it | An embargo ends early at $\mathbf{P}$, $\mathbf{X}$, or $\mathbf{A}$ ([CVD Case State Interactions with the RM and EM Process Models](../process_models/model_interactions/rm_em_cs.md)) |
| $\mathbf{E_x} \prec \mathbf{P_u}$ | Participants publish only after the embargo ends | VP-05-006, VP-05-014 |
| $\mathbf{E_x} \prec \mathbf{X}$ for an exploit a participant publishes | Exploit publishers wait for the embargo to end | VP-14-012 |
| $\mathbf{F}_i \prec \mathbf{E_x^\ast}$ for every vendor $i$ | Every vendor's fix is ready before the embargo ends | VP-14-009 asks participants to extend for trailing vendors; VP-09-007 permits ending at a quorum |
| $\mathbf{E_x} \prec \mathbf{C}_i$ | A participant does not close its report while the embargo is in force | RMB-14-003 |

The first row is close to a statement about when the case forms.
Because a case is created with an embargo in force, $\mathbf{E} \prec \mathbf{P}$ fails mainly when the report arrives, or the case is created, after the vul is already public.

The second row is the sharpest of these.
Any $\mathbf{E_x}$ that follows $\mathbf{P}$ is an $\mathbf{E_x^!}$, because public awareness ends an embargo in force.
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

$\mathbf{Ac}_i \prec \mathbf{P}$ implies $\mathbf{V}_i \prec \mathbf{P}$, because a vendor cannot accept a report it has not received.
It is the stronger claim: it rewards a vendor that engages, not one that only knows.
It also covers the gap between $\mathbf{V}$ and $\mathbf{F}$, where $\mathbb{D}$ has nothing to say.

$\mathbf{Ac}_i \prec \mathbf{F}_i$ does not appear here.
It is enforced: fix readiness can be asserted only in an RM state reachable from Accepted (CSB-18-001).

---

## Multi-party desiderata

[Benchmarking MPCVD](./benchmarking_mpcvd.md) applies $\mathbb{D}$ to each vendor separately and then aggregates.
The orderings below relate one participant's events to another's, so a per-vendor history cannot express them.

| Ordering preference | Meaning | Source |
|---|---|---|
| $\mathbf{V}_i \prec \mathbf{F}_j$ for all affected vendors $i, j$ | Every affected vendor learns of the vul before any vendor's fix is ready | Keeps the trailing vendor's time to fix from starting late |
| $\mathbf{J}_k \prec \mathbf{F}_i$ for each deployer $k$ of vendor $i$'s fix | A deployer is in the case before the fix it deploys is ready | Without it, $\mathbf{D} \prec \mathbf{P}$ is out of reach for a deployer that is not also the vendor |
| $\mathbf{S}_k \prec$ the first case content sent to $k$ | A participant agrees to the embargo before it receives the case | VP-08-006, EMB-11-001 |
| $\mathbf{F}_i \prec \mathbf{P}$ for every vendor $i$ | Every vendor's fix is ready before the vul is public | $\mathbf{F} \prec \mathbf{P}$ from $\mathbb{D}$, quantified over vendors |

The deployer row deserves attention.
The protocol requires no deployer to be invited at all.
In the original single-vendor model, $\mathbf{D}$ is the vendor's deployment or an aggregate over its users.
In a multi-party case, a deployer that joins only after $\mathbf{P}$ cannot achieve $\mathbf{D} \prec \mathbf{P}$, however quickly it acts.

The consent row is partly enforced.
While an embargo is in force, the CASE_MANAGER sends no case ledger entry to a participant that has not agreed to it (CM-10-005).
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
| A participant answers an embargo invitation, rather than letting it time out | PEC: `AGREED` or `DECLINED` over `TIMED_OUT` |
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
| $\mathbf{V}_i \prec \mathbf{F}_i \prec \mathbf{D}_i$ | The vendor fix path ([History Constraints](./possible_histories.md)) |
| $\mathbf{Ac}_i \prec \mathbf{F}_i$ | CSB-18-001 |
| A report is accepted or deferred before it is closed, never closed from Valid | VP-02-004, RMB-14-004 |
| The case is initialized before anyone else is invited and before any embargo change | CM-14-007 |
| An embargo end time is set before the case reaches RM Valid | DUR-07-004 |
| $\mathbf{S}_k \prec$ any case ledger entry sent to $k$, while an embargo is in force | CM-10-005 |

---

## Open problems

The candidates above are proposals.
Three problems stand between them and a measure like the one in [Discriminating Skill and Luck](./discriminating_skill_and_luck.md).

### The baseline needs a new walk

The skill coefficient needs the frequency $f_d$ with which each ordering holds by chance.
For $\mathbb{D}$, that frequency comes from a uniform [random walk](./random_walk.md) over the six-event CS model.
The new events live in a joint space of RM, EM, PEC, and CS states, so their baselines need a walk over that joint space.

The coupling rules between the models change the frequencies, and the change can be large.
Public awareness ends an embargo in force, so $\mathbf{P}$ and $\mathbf{E_x^!}$ arrive together, and fix readiness requires acceptance, so $\mathbf{F}$ can never precede $\mathbf{Ac}$.
A walk that ignores these couplings gives baselines for histories that cannot occur.
How large each $f_d$ is under the coupled walk has not been computed.

### The desiderata are not independent

$\mathbf{Ac}_i \prec \mathbf{P}$ implies $\mathbf{V}_i \prec \mathbf{P}$.
$\mathbf{F}_i \prec \mathbf{E_x^\ast}$ for every vendor, combined with $\mathbf{E_x^\ast} \prec \mathbf{P}$, implies $\mathbf{F}_i \prec \mathbf{P}$ for every vendor.
The skill score in [Reasoning Over Histories](./reasoning_over_histories.md) sums over desiderata, so correlated desiderata count the same skill more than once.
The extended set needs either a weighting or a smaller basis.

### The new events are more observable than the old

[CS Model Limitations](../process_models/cs/cs_model_limitations.md) notes that $\mathbf{D}$ is hard to observe and that $\mathbf{X}$ and $\mathbf{A}$ happen outside the protocol.
Most of the new events are protocol acts: the CASE_MANAGER writes $\mathbf{Ac}_i$, $\mathbf{E}$, $\mathbf{E_x}$, $\mathbf{J}_i$, and $\mathbf{S}_i$ to the case ledger when they happen.
A desideratum between two protocol acts can be measured from the ledger alone.
A desideratum that involves $\mathbf{X}$ or $\mathbf{A}$ inherits their observation problems, as the originals do.

---

## Summary

| Group | Desiderata |
|---|---|
| Embargo | $\mathbf{E} \prec \mathbf{P}, \mathbf{X}, \mathbf{A}$; $\mathbf{E_x^\ast} \prec \mathbf{P}, \mathbf{X}, \mathbf{A}$; $\mathbf{E_x} \prec \mathbf{P_u}$; $\mathbf{E_x} \prec$ a participant's $\mathbf{X}$; $\mathbf{F}_i \prec \mathbf{E_x^\ast}$; $\mathbf{E_x} \prec \mathbf{C}_i$ |
| Report handling | $\mathbf{Ac}_i \prec \mathbf{P}, \mathbf{X}, \mathbf{A}$; $\mathbf{Va}_i \prec \mathbf{P}$ |
| Multi-party | $\mathbf{V}_i \prec \mathbf{F}_j$; $\mathbf{J}_k \prec \mathbf{F}_i$ for deployers; $\mathbf{S}_k \prec$ first content to $k$; $\mathbf{F}_i \prec \mathbf{P}$ for every vendor |
| Path shape | Answered invitations, few revisions, short embargoes, accurate validation |

## Further reading

- [Desirable Histories](./desirable_histories.md) — the twelve original desiderata and the partial order they induce.
- [Timing Metrics Within a Case](./timing_metrics.md) — measuring the intervals between these events, not only their order.
- [Benchmarking MPCVD](./benchmarking_mpcvd.md) — per-vendor histories and how they might aggregate.
- [CVD Case State Interactions with the RM and EM Process Models](../process_models/model_interactions/rm_em_cs.md) — the couplings between the models that these desiderata draw on.
