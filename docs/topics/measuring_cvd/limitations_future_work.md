# Limitations and Future Work

{% include-markdown "../../includes/not_normative.md" %}

This section highlights some limitations of the current work and lays
out a path for improving on those limitations in future work. Broadly,
the opportunities for expanding the model include

- addressing the complexities of tracking CVD and MPCVD cases throughout their lifecycle

- addressing the importance of both state transition probabilities and
    the time interval between them

- options for modeling attacker behavior

- modeling multiple agents

- gathering more data about CVD in the world

- managing the impact of partial information

- working to account for fairness and the complexity of
    MPCVD

## State Explosion

Although our discussion of MPCVD in
§[6.2](#sec:mpcvd){== TODO fix ref to sec:mpcvd ==} and
§[6.2.2](#sec:mpcvd criteria){== TODO fix ref to sec:mpcvd criteria ==} highlights one area in which the number
of states to track can increase dramatically, an even larger problem
could arise in the context of VM efforts even within normal
CVD cases. Our
model casts each event $\sigma \in \Sigma$ as a singular point event,
even though some---such as fix deployed $\mathbf{D}$---would be more
accurately described as diffusion or multi-agent processes.

That is, by the time a vulnerability case reaches the point of
remediating individual instances of vulnerable deployments, every such
instance has its own state to track in regards to whether $\mathbf{D}$
has occurred yet. To apply this model to real world observations, it may
be pragmatic to adapt the event definition to include some defined
threshold criteria.

However, this problem is equivalent to an existing problem in
VM practice: how
best to address the question of whether the fix for a vulnerability has
been deployed across the enterprise. Many organizations find a fixed
quantile SLE to be
a reasonable approach. For example, a stakeholder might set the
SLE that 80% of
known vulnerable systems will be patched within a certain timeframe.
Other organizations might track fix deployments by risk groups, for
example by differentiating between end user systems, servers, and
network infrastructure. They then could observe the deployed fix ratio
for their constituency and mark the event $\mathbf{D}$ as having
occurred when certain thresholds are reached. Nothing in our model
precludes those sorts of roll-up functions from being applied.

## The Model Does Not Address Transition Probabilities

Although we posit a skill-less baseline in which each transition is
equally likely whenever possible within the model, it is a reasonable
criticism to point out that some transitions may be expected to change
conditional on a history already in progress.

For example, many people believe that the publication of exploits
increases the likelihood of attacks. Our model moves toward making this
a testable hypothesis: Does
$p(\mathbf{A}|q \in \mathcal{Q}_X) > p(\mathbf{A}|q \in  \mathcal{Q}_x)$
over some set of cases? Other such hypotheses can be framed in terms of
the model.

Does making vulnerabilities public prior to fix readiness increase
attacks? $$p(\mathbf{A}|q \in fP) > p(\mathbf{A}|q \in FP)?$$ Does
notifying vendors prior to making vulnerability information public
increase the likelihood that fixes will be deployed before attacks are
observed?
$$p(\mathbf{D} \prec \mathbf{A}|\mathbf{V} \prec \mathbf{P}) > p(\mathbf{D} \prec \mathbf{A}|\mathbf{P} \prec \mathbf{V})?$$
The novelty here is not that these questions could not be asked or
answered previously. Rather, it is that the formalism of our model
allows them to be stated concisely and measured in terms of 6 events
$\sigma \in \Sigma$, which points directly to the usefulness of
collecting data about those events as part of ongoing
CVD (including
MPCVD) practices.

## The Model Does Not Achieve a Total Order Over Histories

As described in §[4.4](#sec:h_poset_skill){== TODO fix ref to sec:h_poset_skill ==}, some ambiguity remains regarding
preferences for elements of $\mathbb{D}$. These preferences would need
to be addressed before the model can achieve a total order over
histories $\mathcal{H}$. Specifically, we need to decide whether it is
preferable

- that Fix Ready precede Exploit Publication
    ($\mathbf{F} \prec \mathbf{X}$) or that Vendor Awareness precede
    Public Awareness ($\mathbf{V} \prec \mathbf{P}$)

- that Public Awareness precede Exploit Publication
    ($\mathbf{P} \prec \mathbf{X}$) or that Exploit Publication Precede
    Attacks ($\mathbf{X} \prec \mathbf{A}$)

- that Public Awareness precede Attacks
    ($\mathbf{P} \prec \mathbf{A}$) or Vendor Awareness precede Exploit
    Publication ($\mathbf{V} \prec \mathbf{X}$)

We look forward to the ensuing "would you rather\...?" discussions.

## The Model Has No Sense of Timing

There is no concept of time in this model, but delays between events can
make a big difference in history results. Two cases in which
$\mathbf{F} \prec \mathbf{A}$ would be quite different if the time gap
between these two events was 1 week versus 3 months, as this gap
directly bears on the need for speed in deploying fixes. Organizations
may wish to extend this model by setting timing expectations in addition
to simple precedence preferences. For example, organizations may wish to
specify SLEs for
$\mathbf{V} \prec \mathbf{F}$, $\mathbf{F} \prec \mathbf{D}$,
$\mathbf{F} \prec \mathbf{A}$, and so forth.

Furthermore, in the long run the elapsed time for
$\mathbf{F} \prec \mathbf{A}$ essentially dictates the response time
requirements for VM
processes for system owners. Neither system owners nor vendors get to
choose when attacks happen, so we should expect stochasticity to play a
significant role in this timing. However, if an organization cannot
consistently achieve a shorter lag between $\mathbf{F}$ and $\mathbf{D}$
than between $\mathbf{F}$ and $\mathbf{A}$ (i.e., achieving
$\mathbf{D} \prec \mathbf{A}$) for a sizable fraction of the
vulnerability cases they encounter, it's difficult to imagine that
organization being satisfied with the effectiveness of their
VM program.

## Attacks As Random Events

In the model presented here, attacks are modeled as random events.
However, attacks are not random. At an individual or organization level,
attackers are intelligent adversaries and can be expected to follow
their own objectives and processes to achieve their ends.

Modeling the details of various attackers is beyond the scope of this
model. Thus we believe that a stochastic approach to adversarial actions
is reasonable from the perspective of a vendor or system owner.
Furthermore, if attacks were easily predicted, we would be having a very
different conversation.

## Modeling Multiple Agents

We agree with the reviewer who suggested that an agent-based model could
allow deeper examination of the interactions between stakeholders in
MPCVD. Many of
the mechanisms and proximate causes underlying the events this model
describes are hidden from the model, and would be difficult to observe
or measure even if they were included.

Nevertheless, to reason about different stakeholders' strategies and
approaches to MPCVD, we need a way to measure and compare outcomes. The
model we present here gives us such a framework, but it does so by
making a tradeoff in favor of generality over causal specificity. We
anticipate that future agent-based models of
MPCVD will be
better positioned to address process mechanisms, whereas this model will
be useful to assess outcomes independently of the mechanisms by which
they arise.

## Gather Data About CVD

§[6.1](#sec:benchmarks){== TODO fix ref to sec:benchmarks ==}
discusses how different benchmarks and "reasonable baseline
expectations" might change the results of a skill assessment. It also
proposes how to use observations of the actions a certain team or team
performs to create a baseline which compares other
CVD practitioners
to the skill of that team or teams. Such data could also inform causal
reasoning about certain event orderings and help identify effective
interventions. For example, might causing $\mathbf{X} \prec \mathbf{F}$
be an effective method to improve the chances of
$\mathbf{D} \prec \mathbf{A}$ in cases where the vendor is slow to
produce a fix? Whether it is better to compare the skill of a team to
blind luck via the i.i.d. assumption or to other teams via measurement
remains an open question.

To address questions such as this, future research efforts must collect
and collate a large amount of data about the timing sequences of events
in the model for a variety of stakeholder groups and a variety of
vulnerabilities. Deeper analysis using joint probabilities could then
continue if the modeling choice is to base skill upon a measure from
past observations.

While there is a modeling choice about using the uniformity assumption
versus observations from past CVD (see
§[6.1](#sec:benchmarks){== TODO fix ref to sec:benchmarks ==}), the model does not depend on whether the
uniformity assumption actually holds. We have provided a means to
calculate from observations a deviation from the desired "reasonable
baseline," whether this is based on the i.i.d. assumption or not.
Although, via our research questions, we have provided a method for
evaluating skill in CVD, evaluating the overarching question of
*fairness* in MPCVD requires a much broader sense of
CVD practices.

## Observation May Be Limited

Not all events $\sigma \in \Sigma$, and therefore not all desiderata
$d \in \mathbb{D}$, will be observable by all interested parties. But in
many cases at least some are, which can still help to infer reasonable
limits on the others, as shown in
§[\[sec:inferring_history\]](#sec:inferring_history){== TODO fix ref to sec:inferring_history ==}.

Vendors are in a good position to observe most of the events in each
case. This is even more so if they have good sources of threat
information to bolster their awareness of the $\mathbf{X}$ and
$\mathbf{A}$ events. A vigilant public can also be expected to
eventually observe most of the events, although $\mathbf{V}$ might not
be observable unless vendors, researchers, and/or coordinators are
forthcoming with their notification timelines (as many increasingly
are). $\mathbf{D}$ is probably the hardest event to observe for all
parties, for the reasons described in the timing discussion above.

## CVD Action Rules Are Not Algorithms

The rules given in §[6.8](#sec:cvd_action_rules){== TODO fix ref to sec:cvd_action_rules ==} are not algorithms. We do not propose
them as a set of required actions for every CVD case. However, following Atul Gawande's
lead, we offer them as a mechanism to generate CVD checklists:

> Good checklists, on the other hand are precise. They are efficient, to
> the point, and easy to use even in the most difficult situations. They
> do not try to spell out everything--a checklist cannot fly a plane.
> Instead, they provide reminders of only the most critical and
> important steps--the ones that even the highly skilled professional
> using them could miss. Good checklists are, above all, practical
> [@gawande2011checklist].

## MPCVD Criteria Do Not Account for Equitable Resilience

The proposed criteria for MPCVD in
§[6.2.2](#sec:mpcvd criteria){== TODO fix ref to sec:mpcvd criteria ==} fail to account for either user
populations or their relative importance. For example, suppose an
MPCVD case had a
total of 15 vendors, with 5 vendors representing 95% of the total
userbase achieving highly preferred outcomes and 10 vendors with poor
outcomes representing the remaining 5% of the userbase. The desired
criteria (high median $\alpha$ score with low variance) would likely be
unmet even though most users were protected.

Similarly, a smaller set of vendor/product pairs might represent a
disproportionate concentration of the total risk posed by a
vulnerability.[^12] Again, aggregation across all vendor/product pairs
could be misleading. In fact, risk concentration within a particular
user population may lead to a need for strategies that appear
inequitable at the vendor level while achieving greater outcome equity
at a larger scale.

The core issue is that we lack a utility function to map from observed
case histories to harm reduction.[^13] Potential features of such a
function include aggregation across vendors and/or users. Alternatively,
it may be possible to devise a method for weighting the achieved
histories in an MPCVD case by some proxy for total user risk.
Other approaches remain possible---for example, employing a heuristic to
avoid catastrophic outcomes for all, then applying a weighted sum over
the impact to the remaining users. Future work might also consider
whether criteria other than high median and low variance could be
applied.

Regardless, achieving accurate estimates of such parameters is likely to
remain challenging. Equity in MPCVD may be a topic of future interest to
groups such as the FIRST Ethics SIG[^14].

## MPCVD Is Still Hard

CVD is a wicked
problem, and MPCVD even more so [@householder2017cert]. The
model provided by this white paper offers structure to describe the
problem space where there was little of it to speak of previously.

However, such a model does not significantly alter the complexity of the
task of coordinating the response of multiple organizations, many of
which identify as each others' competitors, in order to bring about a
delicate social good in the face of many incentives for things to go
otherwise. The social, business, and geopolitical concerns and interests
that influence cybersecurity policy across the globe remain at the heart
of the vulnerability disclosure problem for most stakeholders. Our hope
is that the model found here will help to clarify decisions,
communication, and policies that all have their part to play in
MPCVD process
improvement.
