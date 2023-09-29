# Reasoning over Possible Histories {#sec:reasoning}

Our goal in this section is to formulate a way to rank our
undifferentiated desiderata $\mathbb{D}$ from
§[3.2](#sec:desirability){reference-type="ref"
reference="sec:desirability"} in order to develop the concept of CVD
skill and its measurement in §[5](#sec:skill_luck){reference-type="ref"
reference="sec:skill_luck"}. This will provide a baseline expectation
about events (**RQ2)**.

## History Frequency Analysis {#sec:history_frequency_analysis}

As described in §[3.3](#sec:random_walk){reference-type="ref"
reference="sec:random_walk"}, we apply the principle of indifference to
the available transition events $\sigma_{i+1}$ at each state $q$ for
each of the possible histories to compute the expected frequency of each
history, which we denote as $f_h$. The frequency of a history $f_h$ is
the cumulative product of the probability $p$ of each event $\sigma_i$
in the history $h$. We are only concerned with histories that meet our
sequence constraints, namely $h \in \mathcal{H}$.

$$\label{eq:history_freq}
    f_h = \prod_{i=0}^{5} p(\sigma_{i+1}|h_i) %\textrm{ where } \sigma_i \in h \textrm{ and } h \in H$$

Table [3.1](#tab:possible_histories){reference-type="ref"
reference="tab:possible_histories"} displays the value of $f_h$ for each
history. Having an expected frequency ($f_h$) for each history $h$ will
allow us to examine how often we might expect our desiderata
$d \in \mathbb{D}$ to occur across $\mathcal{H}$.

Choosing uniformly over event transitions is more useful than treating
the six-element histories as uniformly distributed. For example,
$\mathbf{P} \prec \mathbf{A}$ in 59% of valid histories, but when
histories are weighted by the assumption of uniform state transitions
$\mathbf{P} \prec \mathbf{A}$ is expected to occur in 67% of the time.
These differences arise due to the dependencies between some states.
Since [CVD]{acronym-label="CVD" acronym-form="singular+short"} practice
is comprised of a sequence of events, each informed by the last, our
uniform distribution over events is more likely a useful baseline than a
uniform distribution over histories.

## Event Order Frequency Analysis {#sec:ordering_frequency_analysis}

Each of the event pair orderings in Table
[3.3](#tab:ordered_pairs){reference-type="ref"
reference="tab:ordered_pairs"} can be treated as a Boolean condition
that either holds or does not hold in any given history. In
§[4.1](#sec:history_frequency_analysis){reference-type="ref"
reference="sec:history_frequency_analysis"} we described how to compute
the expected frequency of each history ($f_h$) given the presumption of
indifference to possible events at each step. We can use $f_h$ as a
weighting factor to compute the expected frequency of event orderings
($\sigma_i \prec \sigma_j$) across all possible histories $H$. Equations
[\[eq:h_ord\]](#eq:h_ord){reference-type="ref" reference="eq:h_ord"} and
[\[eq:d_freq\]](#eq:d_freq){reference-type="ref" reference="eq:d_freq"}
define the frequency of an ordering $f_{\sigma_i \prec \sigma_j}$ as the
sum over all histories in which the ordering occurs
($H^{\sigma_i \prec \sigma_j}$) of the frequency of each such history
($f_h$) as shown in Table
[3.1](#tab:possible_histories){reference-type="ref"
reference="tab:possible_histories"}.

$$\label{eq:h_ord}
    H^{\sigma_i \prec \sigma_j} \stackrel{\mathsf{def}}{=}\{h \in H \textrm{ where } \sigma_i \prec \sigma_j \textrm{ is true for } h \textrm{ and } i \neq j\}$$

$$\label{eq:d_freq}
    f_{\sigma_i \prec \sigma_j} \stackrel{\mathsf{def}}{=}\sum_{h \in H^{\sigma_i \prec \sigma_j}} {f_h}$$

::: {#tab:event_freq}
                   $\mathbf{V}$   $\mathbf{F}$   $\mathbf{D}$   $\mathbf{P}$   $\mathbf{X}$   $\mathbf{A}$
  -------------- -------------- -------------- -------------- -------------- -------------- --------------
  $\mathbf{V}$                0              1              1          0.333          0.667          0.750
  $\mathbf{F}$                0              0              1          0.111          0.333          0.375
  $\mathbf{D}$                0              0              0          0.037          0.167          0.187
  $\mathbf{P}$            0.667          0.889          0.963              0          0.500          0.667
  $\mathbf{X}$            0.333          0.667          0.833          0.500              0          0.500
  $\mathbf{A}$            0.250          0.625          0.812          0.333          0.500              0

  : Expected Frequency of ${row} \prec {col}$ when events are chosen
  uniformly from possible transitions in each state
:::

Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"} displays the results of this calculation.
Required event orderings have an expected frequency of 1, while
impossible orderings have an expected frequency of 0. As defined in
§[3.2](#sec:desirability){reference-type="ref"
reference="sec:desirability"}, each desiderata $d \in \mathbb{D}$ is
specified as an event ordering of the form $\sigma_i \prec \sigma_j$. We
use $f_d$ to denote the expected frequency of a given desiderata
$d \in \mathbb{D}$. The values for the relevant $f_d$ appear in the
upper right of Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"}. Some event orderings have higher expected
frequencies than others. For example, vendor awareness precedes attacks
in 3 out of 4 histories in a uniform distribution of event transitions
($f_{\mathbf{V} \prec \mathbf{A}} = 0.75$), whereas fix deployed prior
to public awareness holds in less than 1 out of 25
($f_{\mathbf{D} \prec \mathbf{P}} = 0.037$) histories generated by a
uniform distribution over event transitions.

## A Partial Order on Desiderata {#desirability}

Any observations of phenomena in which we measure the performance of
human actors can attribute some portion of the outcome to skill and some
portion to chance [@larkey1997skill; @dreef2004measuring]. It is
reasonable to wonder whether good outcomes in [CVD]{acronym-label="CVD"
acronym-form="singular+short"} are the result of luck or skill. How can
we tell the difference?

We begin with a simple model in which outcomes are a combination of luck
and skill.

$$o_{observed} = o_{luck} + o_{skill}$$

In other words, outcomes due to skill are what remains when you subtract
the outcomes due to luck from the outcomes you observe. In this model,
we treat *luck* as a random component: the contribution of chance. In a
world where neither attackers nor defenders held any advantage and
events were chosen uniformly from $\Sigma$ whenever they were possible,
we would expect to see the preferred orderings occur with probability
equivalent to their frequency $f_d$ as shown in Table
[4.1](#tab:event_freq){reference-type="ref" reference="tab:event_freq"}.

Skill, on the other hand, accounts for the outcomes once luck has been
accounted for. So the more likely an outcome is due to luck, the less
skill we can infer when it is observed. As an example, from
Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"} we see that fix deployed before the
vulnerability is public is the rarest of our desiderata with
$f_{\mathbf{D} \prec \mathbf{P}} = 0.037$, and thus exhibits the most
skill when observed. On the other hand, vendor awareness before attacks
is expected to be a common occurrence with
$f_{\mathbf{V} \prec \mathbf{A}} = 0.75$.

We can therefore use the set of $f_d$ to construct a partial order over
$\mathbb{D}$ in which we prefer desiderata $d$ which are more rare (and
therefore imply more skill when observed) over those that are more
common. We create the partial order on $\mathbb{D}$ as follows: for any
pair $d_1,d_2 \in \mathbb{D}$, we say that $d_2$ exhibits less skill
than $d_1$ if $d_2$ occurs more frequently in $\mathcal{H}$ than $d_1$.

$$\label{eq:ordering_d}
(\mathbb{D},\leq_{\mathbb{D}}) \stackrel{\mathsf{def}}{=}d_2 \leq_{\mathbb{D}} d_1 \iff {f_{d_2}} \stackrel{\mathbb{R}}{\geq} {f_{d_1}}$$

Note that the inequalities on the left and right sides of
[\[eq:ordering_d\]](#eq:ordering_d){reference-type="eqref"
reference="eq:ordering_d"} are flipped because skill is inversely
proportional to luck. Also, while $\leq_{\mathbb{D}}$ on the left side
of [\[eq:ordering_d\]](#eq:ordering_d){reference-type="eqref"
reference="eq:ordering_d"} defines a preorder over the poset
$\mathcal{H}$, the $\stackrel{\mathbb{R}}{\geq}$ is the usual ordering
over the set of real numbers. The result is a partial order
$(\mathbb{D},\leq_{\mathbb{D}})$ because a few $d$ have the same $f_d$
($f_{\mathbf{F} \prec \mathbf{X}} = f_{\mathbf{V} \prec \mathbf{P}} = 0.333$
for example). The full Hasse Diagram for the partial order
$(\mathbb{D},\leq_{\mathbb{D}})$ is shown in
Figure [\[fig:d_poset\]](#fig:d_poset){reference-type="ref"
reference="fig:d_poset"}.

## Ordering Possible Histories by Skill {#sec:h_poset_skill}

::: wrapfigure
r0.3
:::

Next we develop a new partial order on $\mathcal{H}$ given the partial
order $(\mathbb{D},\leq_{\mathbb{D}})$ just described. We observe that
$\mathbb{D}^{h}$ acts as a Boolean vector of desiderata met by a given
$h$. Since $0 \leq f_d \leq 1$, simply taking its inverse could in the
general case lead to some large values for rare events. For convenience,
we use $-log(f_d)$ as our proxy for skill. For example, if a desideratum
were found to occur in every case (indicating no skill required),
$f_d=1$ and therefore $-log(1) = 0$. On the other hand, for increasingly
rare desiderata, our skill metric rises:
$\lim_{f_d \to 0} -log(f_d) = +\infty$.

Taking the dot product of $\mathbb{D}^h$ with the set of $-log(f_d)$
values for each $d \in \mathbb{D}$ represented as a vector, we arrive at
a single value representing the skill exhibited for each history $h$.
Careful readers may note that this value is equivalent to the
[TF-IDF]{acronym-label="TF-IDF" acronym-form="singular+short"} score for
a search for the "skill terms" represented by $\mathbb{D}$ across the
corpus of possible histories $\mathcal{H}$.

We have now computed a skill value for every $h \in \mathcal{H}$, which
allows us to sort $\mathcal{H}$ and assign a rank to each history $h$
contained therein. The rank is shown in
Table [3.1](#tab:possible_histories){reference-type="ref"
reference="tab:possible_histories"}. Rank values start at 1 for least
skill up to a maximum of 62 for most skill. Owing to the partial order
$(\mathbb{D},\leq_{\mathbb{D}})$, some $h$ have the same computed skill
values, and these are given the same rank.

The ranks for $h \in \mathcal{H}$ lead directly to a new poset
$(\mathcal{H},\leq_{\mathbb{D}})$. It is an extension of and fully
compatible with $(\mathcal{H},\leq_{H})$ as developed in
§[3.2](#sec:desirability){reference-type="ref"
reference="sec:desirability"}.

The resulting Hasse Diagram would be too large to reproduce here.
Instead, we include the resulting rank for each $h$ as a column in
Table [3.1](#tab:possible_histories){reference-type="ref"
reference="tab:possible_histories"}. In the table, rank is ordered from
least desirable and skillful histories to most. Histories having
identical rank are incomparable to each other within the poset. The
refined poset $(\mathcal{H},\leq_{\mathbb{D}})$ is much closer to a
total order on $\mathcal{H}$, as indicated by the relatively few
histories having duplicate ranks.

The remaining incomparable histories are the direct result of the
incomparable $d$ in $(\mathbb{D},\leq_{\mathbb{D}})$, corresponding to
the branches in Figure
[\[fig:d_poset\]](#fig:d_poset){reference-type="ref"
reference="fig:d_poset"}. Achieving a total order on $\mathbb{D}$ would
require determining a preference for one of each of the following:

-   that fix ready precede exploit publication
    ($\mathbf{F} \prec \mathbf{X}$) or that vendor awareness precede
    public awareness ($\mathbf{V} \prec \mathbf{P}$)

-   that public awareness precede exploit publication
    ($\mathbf{P} \prec \mathbf{X}$) or that exploit publication precede
    attacks ($\mathbf{X} \prec \mathbf{A}$)

-   that public awareness precede attacks
    ($\mathbf{P} \prec \mathbf{A}$) or vendor awareness precede exploit
    publication ($\mathbf{V} \prec \mathbf{X}$)

Recognizing that readers may have diverse opinions on all three items,
we leave further consideration of the answers to these as future work.

This is just one example of how poset refinements might be used to order
$\mathcal{H}$. Different posets on $\mathbb{D}$ would lead to different
posets on $\mathcal{H}$. For example, one might construct a different
poset if certain $d$ were considered to have much higher financial value
when achieved than others.

