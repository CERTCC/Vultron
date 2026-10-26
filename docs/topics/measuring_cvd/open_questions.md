---
stakeholder_type: [process-researcher]
level: 500
page_type: explanation
description: >
  What measuring CVD still leaves open, from transition probabilities and the order of histories to fairness across vendors.
---

# Open Questions

{% include-markdown "../../includes/not_normative.md" %}

This page lists the open questions about measuring Coordinated Vulnerability Disclosure (CVD).
The original research named these questions as limitations of its model.
Since then, the record that a Vultron case keeps has partly answered some of these questions.
For each partly answered question, the page gives the open part first, and then the settled part with a link.
The page is for people who study the CVD process and want to know where the research can go next.

The questions use the six Case State (CS) events of the [Foundations](foundations/index.md):

| Event | Meaning |
|---|---|
| $\evV$ | The vendor is aware of the vul |
| $\evF$ | The fix is ready |
| $\evD$ | The fix is deployed |
| $\evP$ | The public is aware of the vul |
| $\evX$ | An exploit is public |
| $\evA$ | Attacks are observed |

[What a Case Records](what_a_case_records.md) describes how a Vultron case records each of these six events.

The questions also use these terms from the Foundations:

| Term | Meaning |
|---|---|
| History | The order in which the six events occur in one case |
| Desideratum | An order of two events that a case should achieve, for example a fix that is ready before the vul is public; $a \prec b$ means that event $a$ occurs before event $b$ |
| Baseline | How often a desideratum holds by chance |
| Skill coefficient | A score that compares how often a desideratum holds in observed cases with its baseline |

---

## When is a fix deployed?

The Foundations model treats each event as one point in time.
Fix deployment ($\evD$) is not one point in time.
Each vulnerable system has its own deployment state, and the fix reaches the systems over a period of time.
Thus a deployer needs a threshold at which it counts $\evD$ as complete.

Vulnerability management practice already has this question: when is a fix deployed across an enterprise?
Many organizations use a fixed percentage as a Service Level Expectation (SLE).
For example, an SLE can require a fix on 80% of known vulnerable systems within a set time.
Other organizations set a threshold for each risk group, such as end-user systems, servers, and network infrastructure.
These organizations then mark $\evD$ when each risk group reaches its threshold.
The Foundations model permits each of these thresholds, and does not choose one.

Settled: in a Vultron case, each deployer has its own $\evD$, so the case records the deployment of each deployer separately ([What a Case Records](what_a_case_records.md#per-case-and-per-participant-state)).

---

## How likely is each transition?

A transition is the occurrence of the next event in a history.
The Foundations get their baseline from a [random walk](random_walk.md), which gives the same probability to each permitted transition.
A reasonable objection is that the probability of a transition can depend on the events that occurred before it.

For example, many people think that a public exploit makes attacks more likely.
The Foundations model lets you test this belief.
The test asks whether attacks are more probable in cases where an exploit is public than in cases where no exploit is public.
In the notation of the Foundations, $\mathcal{Q}_X$ is the set of case states with a public exploit, and $\mathcal{Q}_x$ is the set without one.
The test is whether $p(\evA \mid q \in \mathcal{Q}_X) > p(\evA \mid q \in \mathcal{Q}_x)$ is true over a set of cases.

Other beliefs have the same form.
One belief is that attacks increase when the vul is public before the fix is ready.
In the formula below, $fP$ is the set of states where the fix is not ready and the vul is public.
$FP$ is the set of states where the fix is ready and the vul is public:

$$p(\evA \mid q \in fP) > p(\evA \mid q \in FP)$$

Another belief is that vendor notification before public awareness makes deployment before attacks more likely:

$$p(\evD \prec \evA \mid \evV \prec \evP) > p(\evD \prec \evA \mid \evP \prec \evV)$$

Researchers could ask these questions before the Foundations model existed.
The model adds a short statement of each question in terms of the six events.
Each statement shows which data a CVD practice must collect to answer the question.

The same question applies to the extended desiderata on [Desiderata from the Process Models](process_model_desiderata.md).
The baselines for the extended desiderata need a random walk over the combined report, embargo, consent, and case state space.
Task [#5072](https://github.com/CERTCC/Vultron/issues/5072){:target="_blank"} records this calculation.

---

## Which desiderata matter more?

[Reasoning Over Histories](reasoning_over_histories.md) does not decide some preferences between desiderata.
Until someone decides these preferences, the desiderata give only a partial order over histories, not a total order.
A total order ranks every history above or below every other history.
A partial order leaves some pairs of histories without a rank.
The open preferences are these three pairs:

| Is it better that… | …or that… |
|---|---|
| The fix is ready before an exploit is public ($\evF \prec \evX$) | The vendor is aware before the public is aware ($\evV \prec \evP$) |
| The public is aware before an exploit is public ($\evP \prec \evX$) | An exploit is public before attacks are observed ($\evX \prec \evA$) |
| The public is aware before attacks are observed ($\evP \prec \evA$) | The vendor is aware before an exploit is public ($\evV \prec \evX$) |

We look forward to the "would you rather" discussions that these pairs start.

---

## What timing should a case meet?

The CS model records the order of events, and does not record time.
Consider two cases where fix readiness ($\evF$) occurs before observed attacks ($\evA$).
In one case, the interval from $\evF$ to $\evA$ is one week.
In the other case, the interval is three months.
These two cases are very different, but the CS model gives them the same score.

Organizations can set time limits as well as orders.
For example, an organization can set an SLE for each of these intervals:

- vendor awareness ($\evV$) to $\evF$
- $\evF$ to $\evD$
- $\evF$ to $\evA$

Which SLEs a program should use, and at what values, is an open question.

Over many cases, the interval from $\evF$ to $\evA$ sets the response time that a deployer must meet.
Deployers and vendors do not choose when attacks occur, so the interval from $\evF$ to $\evA$ is largely random.
Consider a deployer that usually takes longer to deploy a fix than attackers take to attack.
In other words, its interval from $\evF$ to $\evD$ is usually longer than the interval from $\evF$ to $\evA$.
That deployer usually fails to achieve $\evD \prec \evA$, and its vulnerability management is not effective.

Timing data has its own gaps.
The CASE_MANAGER stamps some events when it next handles the case, not when the events occurred.
The CASE_MANAGER does not record some other events at all ([What a Case Records](what_a_case_records.md#data-gaps)).
Each timing measure must decide how to treat these gaps.

Settled: a Vultron case stamps every change that it records, so intervals are measurable, and [Timing Metrics Within a Case](timing_metrics.md) proposes interval measures.

---

## Are attacks random?

The Foundations model treats attacks as random events.
Attacks are not random.
Each attacker is an intelligent adversary with its own objectives.

A model of each attacker is outside the scope of the Foundations model.
We keep the random treatment of attacks as a modeling choice.
For a vendor or a deployer, a random treatment is a reasonable view of adversaries.
If attacks were easy to predict, the problem would be very different.

---

## How do participants' strategies interact?

An agent-based model could show how the strategies of participants interact in Multi-Party CVD (MPCVD).
The Foundations model does not show the causes of its events.
Many of these causes are also difficult to observe.
The Foundations model gives up causal detail to get a general model: it measures outcomes, not the causes of the outcomes.
An agent-based model of MPCVD would be better for the study of causes, but no such model exists yet.

Settled: in Vultron, each participant is an actor with its own store, and actors coordinate only through protocol messages.
The [demo scenarios](../../tutorials/container_demos.md) of the reference implementation run several actors through complete cases, but the demo scenarios do not model strategy.

---

## Where does the data come from?

[Benchmarking CVD](benchmarking.md) discusses how the choice of baseline changes the result of a skill assessment.
Benchmarking CVD proposes a baseline from the observed performance of one or more teams.
Other CVD practitioners are then compared against that baseline.

Data of this kind could also support causal research on the order of events, and help to find effective interventions.
For example, consider a vendor that is slow to make a fix.
In that case, a public exploit before the fix ($\evX \prec \evF$) can perhaps make deployment before attacks ($\evD \prec \evA$) more likely.
It is an open question whether to compare a team against chance or against other teams.

To answer these questions, researchers need event times from many cases, many kinds of participants, and many vuls.
This collection of data does not exist.
The Foundations model does not need the assumption that all transitions are equally likely.
The model measures the difference from a stated baseline, and that baseline can be chance or past observations.

The open part is the collection of event records from the cases of many organizations.

Settled: the ledger of a Vultron case stamps every change ([What a Case Records](what_a_case_records.md)).
Thus each Vultron case gives the order and the intervals of its events as part of normal coordination.

---

## Who can observe what?

Not every party can observe every event.
Thus not every party can measure every desideratum.
In many cases, a party can observe some of the events, and these events can set limits on the events that it cannot observe.
[Observing Skill](observing_skill.md) shows one example of this method.
Which events each party can see, and how well a measure works when events are missing, is open beyond that one example.

Settled: for a Vultron case, [What a Case Records](what_a_case_records.md#who-observes-what) describes which events reach which participants, and which events occur outside the protocol.

---

## Is the multi-party measure fair?

The criteria on [Benchmarking MPCVD](benchmarking_mpcvd.md) do not include the number of users of each vendor, or the importance of those users.

Consider an MPCVD case with 15 vendors:

- 5 vendors have 95% of the users, and these 5 vendors get good outcomes.
- 10 vendors have the other 5% of the users, and these 10 vendors get bad outcomes.

The proposed criterion is a high median skill coefficient across the vendors, with a low variance.
This case probably fails that criterion, but the case protected most users.

A small set of vendor and product pairs can also hold a large part of the risk from a vul.
Thus an aggregate over all vendor and product pairs can give a wrong result.
When risk is concentrated, a good strategy can look unfair to some vendors but give fairer outcomes to users.

!!! ssvc "Thinking about Risk"

    The number of users is one way to think about risk, but it is not the only way.
    [Value density](https://certcc.github.io/SSVC/reference/decision_points/value_density/){:target="_blank"}, as defined in [SSVC](https://certcc.github.io/SSVC/){:target="_blank"}, is another way.

A utility function gives a number for how good an outcome is.
The root problem is that no utility function connects an observed case history to a reduction in harm.
A utility function of this kind can aggregate across vendors, across users, or both.
The utility function can weight each history in an MPCVD case by an estimate of the risk to the users of that history.
The utility function can also first prevent catastrophic outcomes for all users, and then apply a weighted sum over the effect on the remaining users.
Criteria other than a high median and a low variance can also apply.

!!! question "Is Utilitarianism the Best Approach?"

    We have not considered whether utilitarianism is the best approach to these problems.
    If utilitarianism is the best approach, we have not considered which type of utilitarianism is best.
    These questions are interesting and relevant, but they are too far from the main topic of this page.
    [The History of Utilitarianism](https://plato.stanford.edu/entries/utilitarianism-history/){:target="_blank"} is an introduction to the general topic.

Accurate values for these weights and estimates will probably stay difficult to get.
Equity in MPCVD can be a topic for groups such as the [FIRST Ethics SIG](https://www.first.org/global/sigs/ethics/){:target="_blank"}.

---

## In a two-party case

A two-party case has one reporter and one vendor.
A two-party case is a special case of the same model, and most questions on this page apply to it without change.
These questions change:

| Question | In a two-party case |
|---|---|
| Is the multi-party measure fair? | The question does not apply, because the case has only one vendor. |
| How do participants' strategies interact? | The question has only two participants. |
| When is a fix deployed? | The question applies only if the vendor is also a deployer, or a deployer joins the case. |

---

## MPCVD is still hard

[CVD is a wicked problem](https://certcc.github.io/CERT-Guide-to-CVD/topics/principles/wicked_problem){:target="_blank"}, and MPCVD is more difficult than CVD.
The Foundations model gives structure to a problem that had almost no structure before.

But a model does not make coordination much easier.
Coordination of many organizations is difficult, especially when many of them are competitors.
The organizations must work together for a public good, against many incentives to do otherwise.
Social, business, and geopolitical interests shape cybersecurity policy, and these interests stay at the center of vulnerability disclosure.
We hope that the model makes the decisions, communication, and policies that improve MPCVD clearer.

## Further reading

- [What a Case Records](what_a_case_records.md) — the events, clocks, and data gaps that current measures use.
- [Timing Metrics Within a Case](timing_metrics.md) — the intervals that answer part of the timing question.
- [Benchmarking MPCVD](benchmarking_mpcvd.md) — the multi-party measure that the fairness question examines.
- [Recommended Action Rules for CVD](../other_uses/action_rules.md) — the action rules, and why they are a source of checklists, not an algorithm.
