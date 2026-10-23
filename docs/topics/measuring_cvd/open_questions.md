---
stakeholder_type: [process-researcher]
level: 500
page_type: explanation
description: >
  What measuring CVD still leaves open, from transition probabilities and the order of histories to fairness across vendors.
---

# Open Questions

{% include-markdown "../../includes/not_normative.md" %}

This page lists the questions about measuring Coordinated Vulnerability Disclosure (CVD) that remain open.
They began as the limitations named in the original research, and some have since been partly answered by what a Vultron case records.
For each partly answered question, the open part comes first, followed by what is now settled and where it is described.
The page is for people who study the CVD process and want to know where the research could go next.

The questions use the six Case State (CS) events of the [Foundations](foundations/index.md): vendor awareness $\mathbf{V}$, fix ready $\mathbf{F}$, fix deployed $\mathbf{D}$, public awareness $\mathbf{P}$, exploit public $\mathbf{X}$, and attacks observed $\mathbf{A}$.
[What a Case Records](what_a_case_records.md) describes how a Vultron case records each of them.

---

## When is a fix deployed?

The model treats each event as a single point in time.
Fix deployed $\mathbf{D}$ is better described as a diffusion: every vulnerable instance has its own state, and the fix reaches them over time.
To apply the model to real observations, a deployer needs a threshold at which it counts $\mathbf{D}$ as having happened.

This is a question vulnerability management practice already faces: deciding when a fix counts as deployed across an enterprise.
Many organizations use a fixed quantile as a Service Level Expectation (SLE), such as 80% of known vulnerable systems patched within a set time.
Others track deployment by risk group, such as end-user systems, servers, and network infrastructure, and mark $\mathbf{D}$ when each group reaches its threshold.
Nothing in the model precludes such roll-up functions, and the model does not choose one.

The other half of the original state explosion is settled.
In a Vultron case, $\mathbf{D}$ belongs to each deployer, not to the case, so a case with many deployers records each one's deployment separately ([What a Case Records](what_a_case_records.md#per-case-and-per-participant-state)).

---

## How likely is each transition?

The [random walk](random_walk.md) baseline makes each allowed transition equally likely.
It is a reasonable criticism that some transitions become more or less likely given the history so far.

Many people believe, for example, that publishing an exploit makes attacks more likely.
The model turns that belief into a testable hypothesis: is $p(\mathbf{A} \mid q \in \mathcal{Q}_X) > p(\mathbf{A} \mid q \in \mathcal{Q}_x)$ over some set of cases?
Other beliefs take the same form.
Does making a vul public before a fix is ready increase attacks?

$$p(\mathbf{A} \mid q \in fP) > p(\mathbf{A} \mid q \in FP)?$$

Does notifying vendors before the vul is public make it more likely that fixes are deployed before attacks are observed?

$$p(\mathbf{D} \prec \mathbf{A} \mid \mathbf{V} \prec \mathbf{P}) > p(\mathbf{D} \prec \mathbf{A} \mid \mathbf{P} \prec \mathbf{V})?$$

These questions could be asked before.
What the model adds is a concise statement of each in terms of the six events, which shows what data a CVD practice would need to collect to answer it.

The same question applies to the extended desiderata on [Desiderata from the Process Models](process_model_desiderata.md), whose baselines need a walk over the coupled report, embargo, consent, and case state space.
Task [#5072](https://github.com/CERTCC/Vultron/issues/5072){:target="_blank"} records that computation.

---

## Which desiderata matter more?

[Reasoning Over Histories](reasoning_over_histories.md) leaves some preferences between desiderata unresolved.
Until they are resolved, the desiderata induce only a partial order over histories, not a total order.
The open choices are whether it is better

- that Fix Ready precede Exploit Publication ($\mathbf{F} \prec \mathbf{X}$), or that Vendor Awareness precede Public Awareness ($\mathbf{V} \prec \mathbf{P}$);
- that Public Awareness precede Exploit Publication ($\mathbf{P} \prec \mathbf{X}$), or that Exploit Publication precede Attacks ($\mathbf{X} \prec \mathbf{A}$);
- that Public Awareness precede Attacks ($\mathbf{P} \prec \mathbf{A}$), or that Vendor Awareness precede Exploit Publication ($\mathbf{V} \prec \mathbf{X}$).

We look forward to the "would you rather" discussions these invite.

---

## What timing should a case meet?

The CS model has a sense of order and no sense of time.
Two cases with $\mathbf{F} \prec \mathbf{A}$ are very different if one had a week between the events and the other had three months.
Organizations may want timing expectations as well as orderings: SLEs for $\mathbf{V}$ to $\mathbf{F}$, $\mathbf{F}$ to $\mathbf{D}$, $\mathbf{F}$ to $\mathbf{A}$, and so on.
Which SLEs a program should hold itself to, and at what values, is open.

In the long run, the time from $\mathbf{F}$ to $\mathbf{A}$ sets the response time that a deployer's vulnerability management must meet.
Neither deployers nor vendors choose when attacks happen, so that time is largely random.
A deployer that cannot usually make the time from $\mathbf{F}$ to $\mathbf{D}$ shorter than the time from $\mathbf{F}$ to $\mathbf{A}$, which is achieving $\mathbf{D} \prec \mathbf{A}$, has an ineffective program by any reasonable standard.

Timing data has gaps of its own.
Some events are stamped when the CASE_MANAGER next handles the case rather than when they happened, and some are not recorded at all ([What a Case Records](what_a_case_records.md#data-gaps)).
A timing measure has to decide how to treat them.

The intervals themselves are now measurable.
A Vultron case stamps every change it records, and [Timing Metrics Within a Case](timing_metrics.md) proposes the intervals, margins, and dwell times that those stamps support.

---

## Are attacks random?

The model treats attacks as random events.
Attacks are not random: at the level of one attacker, an intelligent adversary follows its own objectives.

Modeling individual attackers is beyond the scope of this model.
We keep the stochastic treatment as a modeling stance, because it is a reasonable view of adversaries from the position of a vendor or a deployer.
If attacks were easy to predict, this would be a very different conversation.

---

## How do participants' strategies interact?

An agent-based model could examine how participants' strategies interact in Multi-Party CVD (MPCVD).
Many of the mechanisms behind the events in this model are hidden from it, and would be hard to observe even if they were included.
The model trades causal detail for generality: it measures outcomes independently of the mechanisms that produce them.
An agent-based model of MPCVD would be better placed to study the mechanisms, and none exists yet.

The protocol side of multiple actors is settled.
In Vultron each participant is an actor with its own identity and its own store, and actors coordinate only by exchanging protocol messages.
The reference implementation's [demo scenarios](../../tutorials/container_demos.md) run several such actors, each in its own container, through complete cases.
They exercise the protocol; they do not model participant strategy.

---

## Where does the data come from?

[Benchmarking CVD](benchmarking.md) discusses how different baselines change the result of a skill assessment.
It proposes using the observed performance of a team or teams as the baseline against which other CVD practitioners are compared.
Such data could also support causal reasoning about event orderings and help find effective interventions.
For example, might forcing $\mathbf{X} \prec \mathbf{F}$ improve the chances of $\mathbf{D} \prec \mathbf{A}$ when a vendor is slow to produce a fix?
Whether to compare a team against chance or against other teams remains open.

Answering such questions needs a large body of event timings, across many kinds of participants and vuls.
That body of data does not exist.
The model does not depend on the uniformity assumption holding: it measures deviation from a stated baseline, whether chance or past observation.

A Vultron case is a source of such data.
Its ledger records every change with a timestamp, so cases run on Vultron produce event orders and intervals as a side effect of coordinating ([What a Case Records](what_a_case_records.md)).
Collecting those records across many organizations' cases is the open part.

---

## Who can observe what?

Not every event, and so not every desideratum, is observable by every interested party.
In many cases at least some are, and those can bound the others, as [Observing Skill](observing_skill.md) shows.
Which events each party can see, and how well a measure holds up when some are missing, is open beyond that one example.

For a Vultron case, much of this is now settled.
[What a Case Records](what_a_case_records.md#who-observes-what) describes which events reach which participants and which happen outside the protocol.

---

## Is the multi-party measure fair?

The criteria proposed on [Benchmarking MPCVD](benchmarking_mpcvd.md) do not account for user populations or their relative importance.
Suppose an MPCVD case has 15 vendors: 5 vendors with 95% of the users reach good outcomes, and 10 vendors with the other 5% reach poor ones.
The proposed criterion, a high median skill score with low variance, would likely fail, even though most users were protected.

A small set of vendor and product pairs can also hold a large share of the risk a vul poses.
Aggregating over all pairs can mislead.
Concentrated risk may even call for strategies that look inequitable among vendors and achieve more equitable outcomes across users.

!!! ssvc "Thinking about Risk"

    User concentration is one way to think about risk, but it is not the only way.
    [Value density](https://certcc.github.io/SSVC/reference/decision_points/value_density/){:target="_blank"}, as defined in [SSVC](https://certcc.github.io/SSVC/){:target="_blank"}, is another.

The underlying problem is that there is no utility function mapping an observed case history to harm reduction.
Such a function might aggregate across vendors, across users, or both.
It might weight each history in an MPCVD case by a proxy for the risk to its users.
It might first avoid catastrophic outcomes for everyone, then apply a weighted sum over the impact on the remaining users.
Criteria other than a high median and low variance may also apply.

!!! question "Is Utilitarianism the Best Approach?"

    We have not considered whether utilitarianism is the best way to approach these problems, or, if it is, which variety suits them best.
    Those questions are interesting and relevant, and too far from the main topic to treat properly here.
    [The History of Utilitarianism](https://plato.stanford.edu/entries/utilitarianism-history/){:target="_blank"} is an introduction to the general topic.

Accurate estimates of such parameters are likely to stay hard to obtain.
Equity in MPCVD may interest groups such as the [FIRST Ethics SIG](https://www.first.org/global/sigs/ethics/){:target="_blank"}.

---

## MPCVD is still hard

[CVD is a wicked problem](https://certcc.github.io/CERT-Guide-to-CVD/topics/principles/wicked_problem){:target="_blank"}, and MPCVD more so.
The model gives structure to a problem space that had little of it before.

A model does not make coordination much less complex.
Coordinating many organizations, many of them competitors, to bring about a delicate social good against many incentives to do otherwise stays hard.
The social, business, and geopolitical interests that shape cybersecurity policy remain at the heart of vulnerability disclosure for most participants.
Our hope is that the model helps clarify the decisions, communication, and policies that each have a part in improving MPCVD.

## Further reading

- [What a Case Records](what_a_case_records.md) — the events, clocks, and data gaps that today's measures work from.
- [Timing Metrics Within a Case](timing_metrics.md) — the intervals that answer part of the timing question.
- [Benchmarking MPCVD](benchmarking_mpcvd.md) — the multi-party measure whose fairness the last question examines.
- [Recommended Action Rules for CVD](../other_uses/action_rules.md) — the action rules, and why they are a source of checklists rather than an algorithm.
