---
stakeholder_type: [process-researcher]
level: 500
page_type: explanation
subject: neutral
description: >
  Ordering preferences beyond the original twelve, distilled from the report, embargo, consent, and multi-party process models.
---

# Desiderata from the Process Models

{% include-markdown "../../includes/not_normative.md" %}

This page proposes new desiderata for Coordinated Vulnerability Disclosure (CVD) cases.
A desideratum is an order of two events that a case should achieve, for example a fix that is ready before the vul is public.

The original research gives twelve desiderata over six events of the Case State (CS) model.
Since then, the protocol has added detailed models of Report Management (RM), Embargo Management (EM), Participant Embargo Consent (PEC), and multi-party participation.
These models give more preferences about which events should occur before which other events.

The page is a draft research proposal for people who study the CVD process.
No part of the page is normative, and no one has tested the new desiderata against case data.

The page uses the events and symbols of [What a Case Records](./what_a_case_records.md), which also tells how the case ledger records each event.
The table below repeats these events:

{% include-markdown "./_case_events.md" %}

The page also uses the skill coefficient ($\alpha_d$) of [Discriminating Skill and Luck](./discriminating_skill_and_luck.md).
The skill coefficient compares how often a desideratum $d$ holds in observed cases with how often $d$ holds by chance.
The process models that the page uses are [RM](../process_models/rm/index.md), [EM](../process_models/em/index.md), and their [interactions with CS](../process_models/model_interactions/index.md).

---

## The twelve original desiderata

The original research orders six events.
The six events are vendor awareness (**V**), fix readiness (**F**), fix deployment (**D**), public awareness (**P**), a public exploit (**X**), and observed attacks (**A**).
The table below gives its twelve desiderata, from the most desirable to the least desirable.
[Desirable Histories](./desirable_histories.md) calls this set of twelve desiderata $\mathbb{D}$, and [What Does *Success* Mean in CVD?](../background/cvd_success.md) explains each desideratum.

{% include-markdown "../../includes/twelve_desiderata.md" %}

The twelve desiderata treat each event as one event for the whole case.
In a case with more than one vendor or deployer, vendor awareness, fix readiness, and fix deployment occur once for each vendor or deployer.
The new desiderata below use the subscripts of the event table to name each vendor and each deployer.

---

## A desideratum is useful only if a case can fail it

A desideratum is useful as a measure of skill only if a case can fail it.
The skill coefficient compares how often an order holds with how often the order holds by chance.
A conforming case is a case in which every participant follows the protocol.
If the protocol enforces an order, the order holds in every conforming case.
Then the observed frequency of the order is 1, and its skill coefficient tells nothing about skill.

The process models contain rules of two kinds:

- A MUST is a requirement that the implementation enforces. An order that a MUST sets is a **conformance ordering**. A history that breaks a conformance ordering shows a broken implementation, not a case without skill.
- A SHOULD, or a preference that a model states without a requirement, is not enforced. A conforming case can break it, so it is a candidate desideratum.

The candidates below come from the second kind of rule.
The end of the page lists the conformance orderings, because a check of these orderings can still find defects.

---

## Events beyond the six

The process models add the events below to the six original events.
The table gives the step of the process model at which each event occurs.

| Event | Process model step |
|---|---|
| Report receipt ($\evR_i$) | RM Start → Received |
| Report validation ($\evVa_i$) | RM → Valid |
| Report acceptance ($\evAc_i$) | RM → Accepted |
| Report closure ($\evC_i$) | RM → Closed |
| Embargo start ($\evE$) | EM → Active, the first time on the case |
| Embargo exit ($\evEx$) | EM → eXited |
| Joining ($\evJ_i$) | Acceptance of the Stub Invite to the case (CM-11-001) |
| Embargo agreement ($\evS_i$) | PEC → `AGREED` |

The [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) records each of these events as an entry in the case ledger.
One exception is the statuses that the case gets when it is created.
These statuses show the creation time, not the time of the decision ([What a Case Records](./what_a_case_records.md#statuses-seated-at-case-creation)).

The embargo start ($\evE$) and the embargo exit ($\evEx$) belong to the whole case, because a case has at most one active embargo.
When an embargo is active, $\evJ_i$ and $\evS_i$ are one event.
The reason is that acceptance of the Stub Invite both joins the case and agrees to the embargo (CM-11-001).
Joining and embargo agreement are separate events only for a participant that joins when no embargo is active, or that answers a later embargo.

### Splitting embargo exit by cause

The same change of state can be a success or a failure, depending on its cause.
Thus the embargo exit is split into three outcomes by cause.

| Split | Meaning |
|---|---|
| Embargo exit on its own terms ($\evExOwn$) | The embargo ends because its end time is reached, or ends early because fixes are ready or deployed |
| Embargo exit on a threat signal ($\evExThreat$) | The embargo ends because of public awareness, a public exploit, or observed attacks |
| Other early embargo exit ($\evExOther$) | The embargo ends early for another reason, or for no recorded reason |

The protocol records this split.
A terminated embargo records its end: `END_TIME_REACHED` or `EARLY`.
When the cause is known, the terminated embargo also records a structured cause: `THREAT_SIGNAL`, `FIX_READY`, `FIX_DEPLOYED`, or `OTHER` (EMB-13-004).

`END_TIME_REACHED`, `FIX_READY`, and `FIX_DEPLOYED` are $\evExOwn$.
`THREAT_SIGNAL` is $\evExThreat$.
An early end with the cause `OTHER`, or with no recorded cause, is $\evExOther$.
Only the CASE_MANAGER can record `THREAT_SIGNAL`, when a case status update sets public awareness, a public exploit, or observed attacks (EMB-13-005).
Thus $\evExOther$ is never a recorded threat signal.

### Public awareness is one event

Public awareness ($\evP$) is not split by its source.
A coordinated publication by a participant and a leak are different causes, but the case cannot tell them apart.

A participant reports public awareness with a case status update that sets P.
The status update asserts that information about the vul is public.
It does not say why the information is public.
A participant can explain the cause in the free text of the activity, but nothing structured records it.

The same is true of a public exploit ($\evX$).
A status update that sets X does not say who published the exploit.
Thus a measure cannot tell an exploit that a participant published from any other public exploit.

---

## Embargo desiderata

An embargo is a means, not an end.
An embargo exists to give vendors time for fix readiness ($\evF$) and fix deployment ($\evD$).
The embargo lets these events occur before $\evP$, a public exploit ($\evX$), and observed attacks ($\evA$).
Thus the embargo desiderata rank below the fix desiderata of the twelve original desiderata.
A case that achieves $\evF \prec \evP$ without an embargo is not a worse case.

| Ordering preference | Meaning | Source |
|---|---|---|
| $\evE \prec \evP$, $\evE \prec \evX$, $\evE \prec \evA$ | An embargo is active before the vul is public, exploited, or attacked | A case starts in EM Active at creation, under a published default or the protocol default ([Default Embargoes](../process_models/em/defaults.md)) |
| $\evExOwn \prec \evP$, $\evExOwn \prec \evX$, $\evExOwn \prec \evA$ | The embargo ends on its own terms, not because a threat signal ended it | An embargo ends early at $\evP$, $\evX$, or $\evA$ ([CVD Case State Interactions with the RM and EM Process Models](../process_models/model_interactions/rm_em_cs.md)) |
| $\evF_i \prec \evExOwn$ for every vendor $i$ | Every vendor's fix is ready before the embargo ends on its own terms | VP-14-009 asks participants to extend for trailing vendors; VP-09-007 permits ending at a quorum |

### An embargo before public awareness

The prototype assumes that every case starts with an embargo.
The embargo is a default that the participants publish, or the protocol default.
Under this assumption, a new case starts in EM Active, unless $\evP$, $\evX$, or $\evA$ already occurred.
In that condition, the case stays in EM None (EP-04-005, EP-04-008).
Thus $\evE \prec \evP$ fails only when the report arrives, or the case is created, after $\evP$, $\evX$, or $\evA$ already occurred.

An implementation that does not start every case with an embargo can fail this desideratum in more ways.
For example, the participants can be slow to agree to an embargo, and the vul can become public before they agree.
Thus the desideratum is itself an argument for default embargoes.
A default embargo is a mechanism that makes the case achieve the desideratum more often.

### An embargo that ends on its own terms

The desideratum of an embargo exit on its own terms before public awareness, a public exploit, and observed attacks is the most useful of these.
Public awareness and a public exploit each end an active embargo (VP-09-001).
Thus any $\evEx$ after $\evP$ or $\evX$ is $\evExThreat$.
Observed attacks SHOULD also end an active embargo (VP-09-003).
Thus $\evEx$ after $\evA$ is usually, but not always, $\evExThreat$.

The desideratum $\evExOwn \prec \evP$ shows that the embargo ended as planned.
Disclosure did not force the end of the embargo.
An embargo that ends as $\evExOther$ fails the desideratum, because it did not end as planned.
But $\evExOther$ is not a threat signal, so the measure does not count it as $\evExThreat$.

This desideratum also covers two preferences that the measure cannot observe directly.
Participants SHOULD NOT publish while an embargo is active (VP-05-006, VP-05-014), and exploit publishers SHOULD NOT release exploit code while an embargo is active (VP-14-012).
The case cannot tell who made the vul public or who published the exploit.
But a participant that publishes during the embargo sets $\evP$ or $\evX$, and the embargo ends on a threat signal.
Thus the case fails $\evExOwn \prec \evP$ or $\evExOwn \prec \evX$.

### Every vendor's fix before the embargo ends on its own terms

The desideratum $\evF_i \prec \evExOwn$ for every vendor is stronger than the protocol requires.
VP-09-007 lets an embargo end when a quorum of vendors has a fix ready, even if some vendors do not.
A vendor without a fix ready at that time is a trailing vendor.

The desideratum gives the higher goal: a fix ready from every vendor before the embargo ends.
A case that ends its embargo at a quorum fails the desideratum once for each trailing vendor.
The measure should count each of these failures.

A lesser outcome is also worth observing.
The case owner can end the embargo early because a quorum of vendors has a fix ready.
The terminated embargo then records the cause `FIX_READY`, with the vendors whose readiness made the quorum (EMB-13-004).

But the protocol does not define a quorum.
The `FIX_READY` cause is a claim of the case owner, and the CASE_MANAGER records it as given (EMB-13-005).
Thus a measure can count the cases that ended at a claimed quorum, but it cannot judge whether the quorum was sufficient.

### A rule that this page does not propose

A participant SHOULD NOT close its report while an embargo is active, unless it first tells the others that it is closing and what its embargo stance is (RMB-14-003).
This page does not make $\evEx \prec \evC_i$ a desideratum.
The desideratum would reward a bad pattern: a participant publishes early, the embargo ends, and then the participant closes its report.

The other desiderata already cover the purpose of the rule.
A participant that publishes early makes the case fail $\evExOwn \prec \evP$.
A vendor that closes its report without a fix fails $\evF_i \prec \evExOwn$.
Also, a closed participant that agreed to the embargo is still bound by the embargo.

The case owner cannot close the case while an embargo is active, because the CASE_MANAGER refuses the close (CM-23-011).
Thus the rule that the case owner does not close the case while an embargo is active is a conformance ordering, not a desideratum.

---

## Report-handling desiderata

The twelve original desiderata treat vendor awareness as the first good event.
The RM model separates awareness from engagement: a vendor can know of a report and still not validate it, accept it, or work on it.

The desiderata below count only the vendors whose reports reach Valid.
The case does not record which vendors the vul affects.
A vendor that the vul does not affect decides that the report is invalid, and a measure cannot tell this decision from a wrong decision about a real vul.
Thus these desiderata measure only the timing of the decisions.
Whether a decision of Invalid was correct is a different preference, validation accuracy, in [Preferences about the path](#preferences-about-the-path).

| Ordering preference | Meaning | Source |
|---|---|---|
| $\evAc_i \prec \evP$, $\evAc_i \prec \evX$, $\evAc_i \prec \evA$ for every vendor $i$ whose report reaches Valid | The vendor has committed to work on the report before the vul is public, exploited, or attacked | [Reward Functions](./reward_functions.md) prefers RM paths that pass through Accepted |
| $\evVa_i \prec \evP$ for every vendor $i$ whose report reaches Valid | A vendor that decides the report is valid does so before the vul is public | Validation is the first RM decision |
| $\evAc_i \prec \evF_i$ for every vendor $i$ | The vendor accepts the report before its fix is ready, rather than deferring or closing it first | CSB-18-001 also permits a fix from Deferred or Closed |

The desideratum $\evVa_i \prec \evP$ is a weaker form of $\evF_i \prec \evP$.
A vendor usually decides that the report is valid before its fix is ready.
Thus a vendor with a fix ready before public awareness usually also has a validation before public awareness.

There is one exception.
A vendor can report fix readiness when its RM state is Closed (CSB-18-001), and the RM state can go from Invalid to Closed without Valid.
Thus a vendor that decides the report is invalid, closes it, and later reports a fix has a fix without a validation.
The protocol permits this history, but it is rare.

The desideratum $\evAc_i \prec \evP$ implies awareness of vendor $i$ before public awareness ($\evV_i \prec \evP$).
The reason is that a vendor cannot accept a report that it has not received.
Thus report acceptance before public awareness is the stronger desideratum.
It rewards a vendor that does work on the report, not a vendor that only knows of the report.
Report acceptance also measures the period between $\evV$ and $\evF$, where the twelve original desiderata have nothing to measure.

The desideratum $\evAc_i \prec \evF_i$ is only partly enforced.
A vendor can report fix readiness only when its RM state is Accepted, Deferred, or Closed (CSB-18-001).
But the RM state can go from Valid to Deferred, or from Received to Closed, without Accepted.
A vendor that defers a report and then releases a fix follows the protocol, but fails the desideratum.
The measure should count this failure.

---

## Multi-party desiderata

[Benchmarking MPCVD](./benchmarking_mpcvd.md) applies the twelve original desiderata to each vendor separately, and then combines the results.
The desiderata below relate the events of one participant to the events of a different participant.
Thus a history of one vendor cannot express these desiderata.

| Ordering preference | Meaning | Source |
|---|---|---|
| $\evV_i \prec \evF_j$ for every vendor $i$ whose report reaches Valid and every vendor $j$ | Every vendor whose report reaches Valid learns of the vul before any vendor's fix is ready | Keeps the trailing vendor's time to fix from starting late |
| $\evF_i \prec \evP$ for every vendor $i$ | Every vendor's fix is ready before the vul is public | $\evF \prec \evP$ from $\mathbb{D}$, quantified over vendors |

The desideratum $\evF_i \prec \evP$ for every vendor states one choice for how to combine the results of the vendors.
Benchmarking MPCVD does not choose how to combine these results, and gives a majority rule and a risk-weighted rule as options.
The rule "every vendor" is the strictest rule, and the embargo desiderata above already use this rule.

### Deployers

This page does not propose a desideratum about when deployers join the case.
Fix deployment can be a better measure of the vulnerability management that follows CVD than of CVD itself.

Some cases have deployers anyway.
For example, a vendor that runs a cloud service also deploys its own fix, and so does an organization that runs its own vulnerability disclosure program.
When a case has deployers, a case in which they join before public awareness ($\evJ_k \prec \evP$) is better than a case in which they join after.
A deployer that joins only after $\evP$ cannot achieve $\evD_k \prec \evP$, however quickly it acts.

But this order is often not achievable, for three reasons:

- It is difficult to tell deployers from the public.
- It is difficult to be fair: a case that includes some deployers must decide which deployers to exclude.
- When the group of deployers becomes large enough, telling the group is the same as telling the public.

Even so, a case can include a small number of large deployers, such as service providers, before publication.
In past cases, this action has protected critical infrastructure before the fix reached everyone else.

The protocol does not require a case to invite a deployer, and the case does not record which fix a deployer deployed.
Thus a measure sees only the deployers that join, and a case that invites no deployers cannot fail an order about deployers.
How to measure deployers in a multi-party case is a question for the measurement of multi-party cases as a whole, which Idea [#5143](https://github.com/CERTCC/Vultron/issues/5143){:target="_blank"} records.

---

## Preferences about the path

Some preferences are not orderings of two events.
These preferences are about the shape of a history: how many steps the history has, or how the participants reached a decision.

| Preference | Process model |
|---|---|
| A participant answers an embargo Invite before its RSVP deadline, rather than leaving it to a pocket veto | PEC: `AGREED` or `DECLINED` over `TIMED_OUT`, not counting the Invites the case's close times out (CM-23-014) |
| A case revises its embargo few times | EM: few passes through Revise |
| An embargo is as short as the fixes allow | [EM Principles](../process_models/em/principles.md) |
| A report is judged correctly: a real vul is Valid and a bogus report is Invalid | RM: validation accuracy |

[Reward Functions](./reward_functions.md) already uses these preferences as criteria for reward functions over RM and EM histories.
This page lists these preferences to make the list complete, not as new proposals.
Order desiderata and path preferences need different measures.
An order desideratum fits the skill coefficient ($\alpha_d$), which counts how often the order holds.
A path preference needs a score over the whole history.

---

## Conformance orderings

The orderings below are enforced by the protocol.
Conformance orderings are not desiderata, because a conforming case cannot fail them.
But a check of case data against the conformance orderings is still useful.
A history that breaks a conformance ordering shows a defect in an implementation.

| Ordering | Requirement |
|---|---|
| $\evV_i \prec \evF_i$ for every vendor $i$ | The vendor fix path ([History Constraints](./possible_histories.md)) |
| $\evF_i \prec \evD_k$ for some vendor $i$, for every deployer $k$ that is not also a vendor | CSB-15-004 |
| $\evF_i$ only once participant $i$'s RM state is Accepted, Deferred, or Closed | CSB-18-001 |
| A report is never closed from Valid | VP-02-004, RMB-14-004 |
| The case is initialized before anyone else is invited and before any embargo change | CM-14-007 |
| An embargo end time is set before an embargo-eligible case reaches RM Valid | DUR-07-004 |
| $\evS_k$ before any case content sent to $k$, while an embargo is active | CM-10-004, CM-10-005 |
| The case owner does not close the case while an embargo is active | CM-23-011 |

Case content includes case ledger entries, case announcements, status broadcasts, and embargo announcements.
Participants SHOULD NOT share the report by other routes with a participant that has not agreed to the embargo either (VP-08-006, EMB-11-001).
The case cannot observe information shared by other routes, so a measure of the case cannot check this preference.

---

## Open problems

The desiderata on this page are proposals.
Three problems must be solved before these desiderata can have a measure like the skill coefficient of [Discriminating Skill and Luck](./discriminating_skill_and_luck.md).

### The baseline needs a new walk

The skill coefficient needs a baseline: the frequency ($f_d$) with which each desideratum holds by chance.
For the twelve original desiderata, the baseline comes from a [random walk](./random_walk.md) over the six-event CS model.
In that random walk, each permitted next event has the same probability.
The new events are in a combined state space of RM, EM, PEC, and CS states.
Thus the baselines of the new desiderata need a random walk over that combined state space.

The rules that connect the models change the baselines, and the change can be large.
For example, public awareness ends an active embargo.
Thus $\evP$ and $\evExThreat$ occur together.
Also, fix readiness requires an RM state of Accepted, Deferred, or Closed.
Thus $\evF$ can never occur before the vendor reaches one of these RM states.

A random walk that ignores these rules gives baselines for histories that cannot occur.
No one has calculated the baseline of each new desideratum under the connected random walk.

### The desiderata are not independent

Some desiderata imply other desiderata:

- $\evAc_i \prec \evP$ implies $\evV_i \prec \evP$, and also implies $\evVa_i \prec \evP$.
- Suppose that every vendor has a fix ready before an embargo exit on its own terms ($\evF_i \prec \evExOwn$). Suppose also that $\evExOwn \prec \evP$. Then every vendor has a fix ready before public awareness ($\evF_i \prec \evP$).

The twelve original desiderata have the same kind of dependence.
For example, $\evF \prec \evP$ implies $\evV \prec \evP$, because a vendor is always aware of the vul before its fix is ready.

The skill score in [Reasoning Over Histories](./reasoning_over_histories.md) adds $-\log(f_d)$ for each desideratum $d$ that a history meets.
A stronger desideratum holds less often by chance than a weaker desideratum that it implies.
Thus the stronger desideratum adds more to the score, and the weaker desideratum adds less.
The score handles the dependence of the twelve original desiderata in this way, and the same method can apply to the new desiderata.

Whether the method is sufficient for the new desiderata depends on their baselines, which Idea [#5072](https://github.com/CERTCC/Vultron/issues/5072){:target="_blank"} records.
If a new desideratum and a desideratum that it implies have nearly the same baseline, the score counts nearly the same skill two times.

### The new events are easier to observe than the original events

[What a Case Records](./what_a_case_records.md#who-observes-what) tells that $\evX$ and $\evA$ occur outside the protocol.
[Open Questions](./open_questions.md#when-is-a-fix-deployed) tells that $\evD$ needs a threshold before anyone can observe it.

Most of the new events are protocol acts.
The CASE_MANAGER writes each of these protocol acts to the case ledger when it admits the act.
These acts include $\evAc_i$, $\evE$, $\evEx$, $\evJ_i$, and $\evS_i$.
The exception is the statuses that the case gets when it is created, which show the creation time.

Thus a measure can get a desideratum between two protocol acts from the ledger alone.
A desideratum that uses $\evX$ or $\evA$ has the same observation problems as the original desiderata.

---

## In a two-party case

A two-party case has one reporter and one vendor.
A two-party case is a special case of the same model, not a different model.
The table below shows how each group of desiderata changes in a two-party case.

| Desiderata | In a two-party case |
|---|---|
| Embargo desiderata | No change. Vendor $i$ is always the one vendor. |
| Report-handling desiderata | No change. Vendor $i$ is always the one vendor. |
| $\evV_i \prec \evF_j$ | Becomes $\evV \prec \evF$, which the vendor fix path already enforces |
| $\evF_i \prec \evP$ for every vendor | Becomes $\evF \prec \evP$ for the one vendor |
| Embargo agreement before case content (a conformance ordering) | Always true for the reporter. The case makes the reporter a signatory of any active embargo when the case is created (CM-14-012). |

---

## Summary

| Group | Desiderata |
|---|---|
| Embargo | $\evE \prec \evP, \evX, \evA$; $\evExOwn \prec \evP, \evX, \evA$; $\evF_i \prec \evExOwn$ for every vendor |
| Report handling | For vendors whose reports reach Valid: $\evAc_i \prec \evP, \evX, \evA$; $\evVa_i \prec \evP$. For every vendor: $\evAc_i \prec \evF_i$ |
| Multi-party | $\evV_i \prec \evF_j$ for vendors $i$ whose reports reach Valid; $\evF_i \prec \evP$ for every vendor |
| Path shape | Answered invitations, few revisions, short embargoes, accurate validation |

## Further reading

- [Desirable Histories](./desirable_histories.md) — the twelve original desiderata and the partial order they induce.
- [What a Case Records](./what_a_case_records.md) — how the case ledger records these events, and the gaps in the ledger.
- [Timing Metrics Within a Case](./timing_metrics.md) — measuring the intervals between these events, not only their order.
- [Benchmarking MPCVD](./benchmarking_mpcvd.md) — per-vendor histories and how they might aggregate.
- [CVD Case State Interactions with the RM and EM Process Models](../process_models/model_interactions/rm_em_cs.md) — the couplings between the models that these desiderata draw on.
