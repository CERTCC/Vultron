# Benchmarking CVD

{% include-markdown "../../includes/not_normative.md" %}

[Observational analysis](./observing_skill.md) supports an affirmative response to
**RQ3**: vulnerability disclosure as currently practiced demonstrates
skill. In both data sets examined, our estimated $\alpha_d$ is positive
for most $d \in \mathbb{D}$. However, there is uncertainty in our
estimates due to the application of the principle of indifference to
unobserved data. This principle assumes a uniform distribution across
event transitions in the absence of CVD, which is an assumption we cannot readily
test. The spread of the estimates in Figures
[5.1](#fig:ms_estimates){== TODO fix ref to fig:ms_estimates ==} and
[5.3](#fig:nvd_estimates){== TODO fix ref to fig:nvd_estimates ==} represents the variance in our samples,
not this assumption-based uncertainty. Our interpretation of $\alpha_d$
values near zero is therefore that they reflect an absence of evidence
rather than evidence that skill is absent. While we cannot rule
definitively on luck or low skill, values of $\alpha_d > 0.9$ should
reliably indicate skillful defenders.

If, as seems plausible from the evidence, it turns out that further
observations of $h$ are significantly skewed toward the higher end of
the poset $(\mathcal{H},\leq_{\mathbb{D}})$, then it may be useful to
empirically calibrate our metrics rather than using the *a priori*
frequencies in [Reasoning over Histories](./reasoning_over_histories.md#event-order-frequency-analysis) as our baseline.
This analysis baseline
would provide context on "more skillful than the average for some set of
teams" rather than more skillful than blind luck.

- [CVD Benchmarks](#cvd-benchmarks) discusses this topic, which should be viewed as an examination of what
"reasonable" should mean in the context of a "reasonable baseline expectation."
- [MPCVD](#mpcvd) suggests how the model might be applied to establish benchmarks for
CVD processes involving any number of participants.

## CVD Benchmarks

As described above, in an ideal CVD situation, each observed history would
achieve all 12 desiderata $\mathbb{D}$. Realistically, this is unlikely
to happen. We can at least state that we would prefer that most cases
reach fix ready before attacks ($\mathbf{F} \prec \mathbf{A}$). Per
Table [4.1](#tab:event_freq){== TODO fix ref to tab:event_freq ==}, even in a world without skill we would
expect $\mathbf{F} \prec \mathbf{A}$ to hold in 73% of cases. This means
that $\alpha_{\mathbf{F} \prec \mathbf{A}} < 0$ for anything less than a
0.73 success rate. In fact, we propose to generalize this for any
$d \in \mathbb{D}$, such that $\alpha_d$ should be greater than some
benchmark constant $c_d$:

$$\alpha_d \geq c_d \geq 0$$

where $c_d$ is a based on observations of $\alpha_d$ collected across
some collection of CVD cases.

We propose as a starting point a naïve benchmark of $c_d = 0$. This is a
low bar, as it only requires that CVD actually do better than possible events
which are independent and identically distributed (i.i.d.) within each
case. For example, given a history in which
$(\mathbf{V}, \mathbf{F}, \mathbf{P})$ have already happened (i.e.,
state $q \in VFdPxa$), $\mathbf{D}$, $\mathbf{X}$, or $\mathbf{A}$ are
equally likely to occur next.

The i.i.d. assumption may not be warranted. We anticipate that event
ordering probabilities might be conditional on history: for example,
exploit publication may be more likely when the vulnerability is public
($p(\mathbf{X}|q \in \mathcal{Q}_P) > p(\mathbf{X}|q \in \mathcal{Q}_p)$)
or attacks may be more likely when an exploit is public
($p(\mathbf{A}|q \in \mathcal{Q}_{X}) > p(\mathbf{A}|q \in \mathcal{Q}_{x})$).
If the i.i.d. assumption fails to hold for transition events
$\sigma \in \Sigma$, observed frequencies of $h \in \mathcal{H}$ could
differ significantly from the rates predicted by the uniform probability
assumption behind Table [4.1](#tab:event_freq){== TODO fix ref to tab:event_freq ==}.

Some example suggestive observations are:

- There is reason to suspect that only a fraction of vulnerabilities
    ever reach the *exploit public* event $\mathbf{X}$, and fewer still
    reach the *attack* event $\mathbf{A}$. Recent work by the Cyentia
    Institute found that "5% of all CVEs are both observed within
    organizations AND known to be exploited" [@cyentia2019getting],
    which suggests that $f_{\mathbf{D} \prec \mathbf{A}} \approx 0.95$.

- Likewise, $\mathbf{D} \prec \mathbf{X}$ holds in 28 of 70 (0.4) $h$.
    However Cyentia found that "15.6% of all open vulnerabilities
    observed across organizational assets in our sample have known
    exploits" [@cyentia2019getting], which suggests that
    $f_{\mathbf{D} \prec \mathbf{X}} \approx 0.844$.

We might therefore expect to find many vulnerabilities remaining
indefinitely in $VFDPxa$.

On their own these observations can equally well support the idea that
we are broadly observing skill in vulnerability response, rather than
that the world is biased from some other cause. However, we could choose
a slightly different goal than differentiating skill and "blind luck" as
represented by the i.i.d. assumption. One could aim to measure "more
skillful than the average for some set of teams" rather than more
skillful than blind luck.

If this were the "reasonable" baseline expectation (**RQ2**), the
primary limitation is available observations. This model helps overcome
this limitation because it provides a clear path toward collecting
relevant observations. For example, by collecting dates for the six
$\sigma \in \Sigma$ for a large sample of vulnerabilities, we can get
better estimates of the relative frequency of each history $h$ in the
real world. It seems as though better data would serve more to improve
benchmarks rather than change expectations of the role of chance.

As an applied example, if we take the first item in the above list as a
broad observation of $f_{\mathbf{D} \prec \mathbf{A}} = 0.95$, we can
plug into [\[eq:alpha_freq\]](#eq:alpha_freq){== TODO fix ref to eq:alpha_freq ==} to get a potential benchmark of
$\alpha_{\mathbf{D} \prec \mathbf{A}} = 0.94$, which is considerably
higher than the naïve generic benchmark $\alpha_d = 0$. It also implies
that we should expect actual observations of histories
$h \in \mathcal{H}$ to skew toward the 19 $h$ in which
$\mathbf{D} \prec \mathbf{A}$ nearly 20x as often as the 51 $h$ in which
$\mathbf{A} \prec \mathbf{D}$. Similarly, if we interpret the second
item as a broad observation of
$f_{\mathbf{D} \prec \mathbf{X}} = 0.844$, we can then compute a
benchmark $\alpha_{\mathbf{D} \prec \mathbf{X}} = 0.81$, which is again
a significant improvement over the naïve $\alpha_d = 0$ benchmark.

## MPCVD

MPCVD is the
process of coordinating the creation, release, publication, and
potentially the deployment of fixes for vulnerabilities across a number
of vendors and their respective products. The need for
MPCVD arises due
to the inherent nature of the software supply chain
[CERT Guide to CVD](https://vuls.cert.org/confluence/display/CVD). A vulnerability that affects a low-level
component (such as a library or operating system API) can require fixes
from both the originating vendor and any vendor whose products
incorporate the affected component. Alternatively, vulnerabilities are
sometimes found in protocol specifications or other design-time issues
where multiple vendors may have each implemented their own components
based on a vulnerable design.
§[6.2.1](#sec:mpcvd_states){== TODO fix ref to sec:mpcvd_states ==} applies the state-based view of our model
to MPCVD, while
§[6.2.2](#sec:mpcvd criteria){== TODO fix ref to sec:mpcvd criteria ==} addresses the topic from the possible
history perspective.

### State Tracking in MPCVD

Applying our state-based model to MPCVD requires a forking approach to the state
tracking. At the time of discovery, the vulnerability is in state
$vfdpxa$. Known only to its finder, the vulnerability can be described
by that singular state.

As it becomes clear that the vulnerability affects multiple vendors'
products, both finder/reporters and coordinators might begin to track
the state of each individual vendor as a separate instance of the model.
For example, if 3 vendors are known to be affected, but only 1 has been
notified, the case might be considered to be in a superposition[^5] of
states $\{Vfdpxa,vfdpxa,vfdpxa\}$.

Each vendor, in turn, might then ascertain whether they are able to
produce fixes for all their available products at once, or if those
fixes will be staggered over time. In either case, the vendor might
track the case as a superposition of states for each affected product
dependent on its fix readiness status. For example, a vendor might have
four products affected, with two in the fix-ready state and two fixes
still in progress. Should they opt for transparency into their internal
process, they might communicate their status as the superposition of
$\{VFdpxa,VFdpxa,Vfdpxa,Vfdpxa\}$. Alternatively, they might choose to
only share the lowest state across their products, which in this example
would be $\{Vfdpxa\}$.

This implies a need to expand our notation. In the
MPCVD case, we
need to think of each state $q \in \mathcal{Q}$ as a set of states
$q_M$: $$q_M \stackrel{\mathsf{def}}{=}\{ q_1,q_2,\dots,q_n \}$$

where $q_i$ represents the state $q$ for the $i$th affected vendor
and/or product. For example, $\{ {Vfdpxa}_1, {vfdpxa}_2 \}$ would
represent the state in which vendor 1 has been notified but vendor 2 has
not.

State transitions across vendors need not be simultaneous. Very often,
vendor notification occurs as new products and vendors are identified as
affected in the course of analyzing a vulnerability report. So the
individual events $\mathbf{V}_i$ in $\mathbf{V}_M$ (representing the
status of all the vendor notifications) might be spread out over a
period of time.

Some transitions are more readily synchronized than others. For example,
if an MPCVD case
is already underway, and information about the vulnerability appears in
a public media report, we can say that $\mathbf{P}_M$ occurred
simultaneously for all coordinating vendors.

Regardless, in the maximal case, each vendor-product pair is effectively
behaving independently of all the others. Thus the maximum
dimensionality of the MPCVD model for a case is
$$D_{max} = 5 * N_{vprod}$$

where $N_{vprod}$ represents the number of vendor-product pairs.

This is of course undesirable, as it would result in a wide distribution
of realized histories that more closely resemble the randomness
assumptions outlined above than a skillful, coordinated effort. Further
discussion of measuring MPCVD skill can be found in
[6.2.2](#sec:mpcvd criteria){== TODO fix ref to sec:mpcvd criteria ==}. For now, though, we posit that the goal
of a good MPCVD
process is to reduce the dimensionality of a given
MPCVD case as
much as is possible (i.e., to the 5 dimensions of a single vendor
CVD case we have
presented above). Experience shows that a full dimension reduction is
unlikely in most cases, but that does not detract from the value of
having the goal.

Vendors may be able to reduce their internal tracking
dimensionality---which may be driven by things like component reuse
across products or product lines---through in-house coordination of fix
development processes. Within an individual vendor organization,
PSIRTs are a common
organizational structure to address this internal coordination process.
The FIRST PSIRT
Services Framework provides guidance regarding vendors' internal
processes for coordinating vulnerability response [@first2020psirt].
Additional guidance can be found in ISO-IEC 30111 [@ISO30111].

Regardless, the cross-vendor dimension is largely the result of
component reuse across vendors, for example through the inclusion of
third party libraries or OEM SDKs. Visibility of cross-vendor component reuse
remains an unsolved problem, although efforts such as
NTIA's
SBOM [@ntia_sbom]
efforts are promising in this regard. Thus, dimensionality reduction can
be achieved through both improved transparency of the software supply
chain and the process of coordination toward synchronized state
transitions, especially for $\mathbf{P}$, if not for $\mathbf{F}$ and
$\mathbf{D}$ as well.

As a result of the dimensionality problem, coordinators and other
parties to an MPCVD case need to decide how to apply
disclosure policy rules in cases where different products or vendors
occupy different case states with potentially contradictory recommended
actions. For example, when four out of five vendors involved in a case
have reached $VFdpxa$ and are ready to publish, but the fifth is still
in $Vfdpxa$. Essentially this can be expected to take the form of a
weighting function that acts on a vector of case states, and outputs a
set of recommended actions derived from those states.

One possible function would be to apply a simple voting heuristic such
as waiting for a simple majority of vendors to reach a state before
taking action as that state recommends. In our 4/5 $VFdpxa$ example, the
coordinating parties would simply behave as if the case were in that
state for all. Another could be to weight vendors and products by some
other factor, such as size of the installed user base, or even based on
a risk analysis of societal costs associated with potential actions.
Here we acknowledge that our example is under-specified: does the fifth
vendor (the one in $Vfdpxa$) represent a sizable fraction of the total
user base? Or does it concentrate the highest risk use cases for the
software? Challenges in efficiently assessing consistent answers to
these questions are easy to imagine. The status quo for
MPCVD appears
consistent with defaulting to simple majority in the absence of
additional information, with consideration given to the distribution of
both users and risk on a case-by-case basis. At present, there is no
clear consensus on such policies, although we hope that future work can
use the model presented here to formalize the necessary analysis.

### Integrating FIRST MPCVD Guidance

FIRST has
published MPCVD
guidance [@first2020mpcvd]. Their guidance describes four use cases,
along some with variations. Each use case variant includes a list of
potential causes along with recommendations for prevention and responses
when the scenario is encountered. A mapping of which use cases and
variants apply to which subsets of states is given in Table
[6.1](#tab:first_use_cases){== TODO fix ref to tab:first_use_cases ==}.

{== TODO fix table here ==}
<!-- 
:::
           States           FIRST Use Case  Description
  ------------------------ ----------------------------------------------------------------------- ----------------------------------------------------------------------------------------------
            n/a                                               0                                    No vulnerability exists
          ${VFDp}$                                            1                                    Vulnerability with no affected users
           ${Vp}$                                        1 Variant 1                               Product is deployed before vulnerability is discovered or fixed
           ${f}$                                              2                                    Vulnerability with coordinated disclosure
          ${fdP}$                                        2 Variant 1                               Finder makes the vulnerability details public prior to remediation
          ${VFdP}$                                       2 Variant 2                               Users do not deploy remediation immediately
     (multiparty sync)                                   2 Variant 3                               Missing communication between upstream and downstream vendors
          ${VfdP}$                                       2 Variant 4                               Vendor makes the vulnerability details public prior to remediation
          ${Vfd}$                                        2 Variant 5                               Vendor does not remediate a reported vulnerability
     (multiparty sync)                                   2 Variant 6                               Missing communication between peer vendors impedes coordination
          ${fdP}$                                        2 Variant 7                               Coordinator makes vulnerability details public prior to remediation
     ${Vfdp}$, ${vfdp}$                                  2 Variant 8                               Finder reports a vulnerability to one vendor that may affect others using the same component
          ${fdP}$                                             3                                    Public disclosure of limited vulnerability information prior to remediation
   ${vP}$, ${vX}$, ${vA}$                                     4                                    Public disclosure or exploitation of vulnerability prior to vendor awareness
     ${vfPX}$, ${vfPA}$                                  4 Variant 1                               Finder publishes vulnerability details and vulnerability is exploited
          ${vpA}$                                        4 Variant 2                               Previously undisclosed vulnerability used in attacks

  : Applicability of FIRST MPCVD scenarios to subsets of states in our
  model
:::

-->

### MPCVD Benchmarks

A common problem in MPCVD is that of fairness: coordinators are
often motivated to optimize the CVD process to maximize the deployment of
fixes to as many end users as possible while minimizing the exposure of
users of other affected products to unnecessary risks.

The model presented in this paper provides a way for coordinators to
assess the effectiveness of their MPCVD cases. In an
MPCVD case, each
vendor/product pair effectively has its own 6-event history $h_a$. We
can therefore recast MPCVD as a set of histories $\mathcal{M}$ drawn
from the possible histories $\mathcal{H}$:
$$\mathcal{M} = \{ h_1,h_2,...,h_m \textrm{ where each } h_a \in H \}$$
Where $m = |\mathcal{M}| \geq 1$. The edge case when $|\mathcal{M}| = 1$
is simply the regular (non-multiparty) case.

We can then set desired criteria for the set $\mathcal{M}$, as in the
benchmarks described in §[6.1](#sec:benchmarks){== TODO fix ref to sec:benchmarks ==}. In the MPCVD case, we propose to generalize the
benchmark concept such that the median $\Tilde{\alpha_d}$ should be
greater than some benchmark constant $c_d$:

$$\Tilde{\alpha_d} \geq c_d \geq 0$$

In real-world cases where some outcomes across different vendor/product
pairs will necessarily be lower than others, we can also add the
criteria that we want the variance of each $\alpha_d$ to be low. An
MPCVD case having
high median $\alpha_d$ with low variance across vendors and products
involved will mean that most vendors achieved acceptable outcomes.

To summarize:

- The median $\alpha_d$ for all histories $h \in \mathcal{M}$ should
    be positive and preferably above some benchmark constant $c_d$,
    which may be different for each $d \in \mathbb{D}$.

    $$Median(\{ \alpha_d(h) : h \in \mathcal{M} \}) \geq c_d > 0$$

- The variance of each $\alpha_d$ for all histories
    $h \in \mathcal{M}$ should be low. The constant $\varepsilon$ is
    presumed to be small.

    $$\sigma^2(\{ \alpha_d(h) : h \in \mathcal{M} \}) \leq \varepsilon$$
