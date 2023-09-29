# Discussion {#sec:discussion}

The observational analysis in
§[5.2](#sec:observation){reference-type="ref"
reference="sec:observation"} supports an affirmative response to
**RQ3**: vulnerability disclosure as currently practiced demonstrates
skill. In both data sets examined, our estimated $\alpha_d$ is positive
for most $d \in \mathbb{D}$. However, there is uncertainty in our
estimates due to the application of the principle of indifference to
unobserved data. This principle assumes a uniform distribution across
event transitions in the absence of CVD, which is an assumption we cannot readily
test. The spread of the estimates in Figures
[5.1](#fig:ms_estimates){reference-type="ref"
reference="fig:ms_estimates"} and
[5.3](#fig:nvd_estimates){reference-type="ref"
reference="fig:nvd_estimates"} represents the variance in our samples,
not this assumption-based uncertainty. Our interpretation of $\alpha_d$
values near zero is therefore that they reflect an absence of evidence
rather than evidence that skill is absent. While we cannot rule
definitively on luck or low skill, values of $\alpha_d > 0.9$ should
reliably indicate skillful defenders.

If, as seems plausible from the evidence, it turns out that further
observations of $h$ are significantly skewed toward the higher end of
the poset $(\mathcal{H},\leq_{\mathbb{D}})$, then it may be useful to
empirically calibrate our metrics rather than using the *a priori*
frequencies in Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"} as our baseline. This analysis baseline
would provide context on "more skillful than the average for some set of
teams" rather than more skillful than blind luck.
§[6.1](#sec:benchmarks){reference-type="ref" reference="sec:benchmarks"}
discusses this topic, which should be viewed as an examination of what
"reasonable" in **RQ2** should mean in the context of "reasonable
baseline expectation."

§[6.2](#sec:mpcvd){reference-type="ref" reference="sec:mpcvd"} suggests
how the model might be applied to establish benchmarks for
CVD processes
involving any number of participants, which closes the analysis of
**RQ1** in relation to MPCVD. §[6.3](#sec:roles){reference-type="ref"
reference="sec:roles"} surveys the stakeholders in
CVD and how they
might use our model; the stakeholders are vendors, system owners, the
security research community, coordinators, and governments. In
particular, we focus on how these stakeholders might respond to the
affirmative answer to **RQ3** and a method to measure skill in a way
more tailored to each stakeholder group.
§[6.4](#sec:policy_formalism){reference-type="ref"
reference="sec:policy_formalism"} discusses the potential for
formalizing disclosure policy specifications using the model.
§[6.5](#sec:defining_common_terms){reference-type="ref"
reference="sec:defining_common_terms"} offers formal definitions of some
common terms in vulnerability disclosure. We then proceed to address
vulnerability response situation awareness in
§[6.6](#sec:situation_awareness){reference-type="ref"
reference="sec:situation_awareness"}, with a brief note about the
VEP in relation to
this model in §[6.7](#sec:vep){reference-type="ref"
reference="sec:vep"}. Finally, a set of state-based rules for
CVD actions is
given in §[6.8](#sec:cvd_action_rules){reference-type="ref"
reference="sec:cvd_action_rules"}.

## CVD Benchmarks {#sec:benchmarks}

As described above, in an ideal CVD situation, each observed history would
achieve all 12 desiderata $\mathbb{D}$. Realistically, this is unlikely
to happen. We can at least state that we would prefer that most cases
reach fix ready before attacks ($\mathbf{F} \prec \mathbf{A}$). Per
Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"}, even in a world without skill we would
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
assumption behind Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"}.

Some example suggestive observations are:

-   There is reason to suspect that only a fraction of vulnerabilities
    ever reach the *exploit public* event $\mathbf{X}$, and fewer still
    reach the *attack* event $\mathbf{A}$. Recent work by the Cyentia
    Institute found that "5% of all CVEs are both observed within
    organizations AND known to be exploited" [@cyentia2019getting],
    which suggests that $f_{\mathbf{D} \prec \mathbf{A}} \approx 0.95$.

-   Likewise, $\mathbf{D} \prec \mathbf{X}$ holds in 28 of 70 (0.4) $h$.
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
plug into [\[eq:alpha_freq\]](#eq:alpha_freq){reference-type="eqref"
reference="eq:alpha_freq"} to get a potential benchmark of
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

## MPCVD {#sec:mpcvd}

MPCVD is the
process of coordinating the creation, release, publication, and
potentially the deployment of fixes for vulnerabilities across a number
of vendors and their respective products. The need for
MPCVD arises due
to the inherent nature of the software supply chain
[@householder2017cert]. A vulnerability that affects a low-level
component (such as a library or operating system API) can require fixes
from both the originating vendor and any vendor whose products
incorporate the affected component. Alternatively, vulnerabilities are
sometimes found in protocol specifications or other design-time issues
where multiple vendors may have each implemented their own components
based on a vulnerable design.
§[6.2.1](#sec:mpcvd_states){reference-type="ref"
reference="sec:mpcvd_states"} applies the state-based view of our model
to MPCVD, while
§[6.2.2](#sec:mpcvd criteria){reference-type="ref"
reference="sec:mpcvd criteria"} addresses the topic from the possible
history perspective.

### State Tracking in MPCVD {#sec:mpcvd_states}

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
[6.2.2](#sec:mpcvd criteria){reference-type="ref"
reference="sec:mpcvd criteria"}. For now, though, we posit that the goal
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

##### Integrating FIRST MPCVD Guidance

FIRST has
published MPCVD
guidance [@first2020mpcvd]. Their guidance describes four use cases,
along some with variations. Each use case variant includes a list of
potential causes along with recommendations for prevention and responses
when the scenario is encountered. A mapping of which use cases and
variants apply to which subsets of states is given in Table
[6.1](#tab:first_use_cases){reference-type="ref"
reference="tab:first_use_cases"}.

::: {#tab:first_use_cases}
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

### MPCVD Benchmarks {#sec:mpcvd criteria}

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
benchmarks described in §[6.1](#sec:benchmarks){reference-type="ref"
reference="sec:benchmarks"}. In the MPCVD case, we propose to generalize the
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

-   The median $\alpha_d$ for all histories $h \in \mathcal{M}$ should
    be positive and preferably above some benchmark constant $c_d$,
    which may be different for each $d \in \mathbb{D}$.

    $$Median(\{ \alpha_d(h) : h \in \mathcal{M} \}) \geq c_d > 0$$

-   The variance of each $\alpha_d$ for all histories
    $h \in \mathcal{M}$ should be low. The constant $\varepsilon$ is
    presumed to be small.

    $$\sigma^2(\{ \alpha_d(h) : h \in \mathcal{M} \}) \leq \varepsilon$$

## CVD Roles and Their Influence {#sec:roles}

CVD stakeholders
include vendors, system owners, the security research community,
coordinators, and governments [@householder2017cert]. Of interest here
are the main roles: *finder/reporter*, *vendor*, *deployer*, and
*coordinator*. Each of the roles corresponds to a set of transitions
they can cause. For example, a *coordinator* can notify the *vendor*
($\mathbf{V}$) but not create the fix ($\mathbf{F}$), whereas a *vendor*
can create the fix but not notify itself (although a *vendor* with an
in-house vulnerability discovery capability might also play the role of
a *finder/reporter* as well). A mapping of CVD Roles to the transitions they can control
can be found in Table [6.2](#tab:cvd_roles){reference-type="ref"
reference="tab:cvd_roles"}. We also included a role of *adversary* just
to cover the $\mathbf{A}$ transition.

::: {#tab:cvd_roles}
        Role         $\mathbf{V}$   $\mathbf{F}$   $\mathbf{D}$   $\mathbf{P}$   $\mathbf{X}$   $\mathbf{A}$
  ----------------- -------------- -------------- -------------- -------------- -------------- --------------
   Finder/Reporter                    $\cdot$        $\cdot$                                      $\cdot$
       Vendor          $\cdot$                       $\cdot$                                      $\cdot$
      Deployer         $\cdot$        $\cdot$                       $\cdot$        $\cdot$        $\cdot$
     Coordinator                      $\cdot$        $\cdot$                                      $\cdot$
      Adversary        $\cdot$        $\cdot$        $\cdot$        $\cdot$        $\cdot$     

  : CVD Roles and
  the transitions they can control. Roles can be combined (vendor +
  deployer, finder + coordinator, etc.). Roles are based on
  [@householder2017cert].
:::

Different stakeholders might want different things, although most
benevolent parties will likely seek some subset of $\mathbb{D}$. Because
$\mathcal{H}$ is the same for all stakeholders, the expected frequencies
shown in Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"} will be consistent across any such
variations in desiderata.

::: {#tab:stakeholder_order}
  ------------------------------- ------------------ ------------------ ------------------
                                        Vendor            SysOwner         Coordinator
  $d \in \mathbb{D}$               ($\mathbb{D}_v$)   ($\mathbb{D}_s$)   ($\mathbb{D}_c$)
  $\mathbf{V} \prec \mathbf{P}$          yes              maybe^4^             yes
  $\mathbf{V} \prec \mathbf{X}$          yes              maybe^4^             yes
  $\mathbf{V} \prec \mathbf{A}$          yes              maybe^4^             yes
  $\mathbf{F} \prec \mathbf{P}$          yes              maybe^5^             yes
  $\mathbf{F} \prec \mathbf{X}$          yes                yes                yes
  $\mathbf{F} \prec \mathbf{A}$          yes                yes                yes
  $\mathbf{D} \prec \mathbf{P}$        maybe^1^           maybe^1^             yes
  $\mathbf{D} \prec \mathbf{X}$        maybe^2^           maybe^5^             yes
  $\mathbf{D} \prec \mathbf{A}$        maybe^2^             yes                yes
  $\mathbf{P} \prec \mathbf{X}$          yes                yes                yes
  $\mathbf{P} \prec \mathbf{A}$          yes                yes                yes
  $\mathbf{X} \prec \mathbf{A}$        maybe^3^           maybe^3^           maybe^3^
  ------------------------------- ------------------ ------------------ ------------------

  : Ordering Preferences for Selected Stakeholders.
:::

::: tablenotes
^1^ When vendors control deployment, both vendors and system owners
likely prefer $\mathbf{D} \prec \mathbf{P}$. When system owners control
deployment, $\mathbf{D} \prec \mathbf{P}$ is impossible.

^2^ Vendors should care about orderings involving $\mathbf{D}$ when they
control deployment, but might be less concerned if deployment
responsibility is left to system owners.

^3^ Exploit publication can be controversial. To some, it enables
defenders to test deployed systems for vulnerabilities or detect
attempted exploitation. To others, it provides unnecessary adversary
advantage.

^4^ System owners may only be concerned with orderings involving
$\mathbf{V}$ insofar as it is a prerequisite for $\mathbf{F}$.

^5^ System owners might be indifferent to $\mathbf{F} \prec \mathbf{P}$
and $\mathbf{D} \prec \mathbf{X}$ depending on their risk tolerance.
:::

A discussion of some stakeholder preferences is given below, while a
summary can be found in Table
[6.3](#tab:stakeholder_order){reference-type="ref"
reference="tab:stakeholder_order"}. We notate these variations of the
set of desiderata $\mathbb{D}$ with subscripts: $\mathbb{D}_v$ for
vendors, $\mathbb{D}_s$ for system owners, $\mathbb{D}_c$ for
coordinators, and $\mathbb{D}_g$ for governments. In
Table [3.3](#tab:ordered_pairs){reference-type="ref"
reference="tab:ordered_pairs"} we defined a preference ordering between
every possible pairing of events, therefore $\mathbb{D}$ is the largest
possible set of desiderata. We thus expect the desiderata of benevolent
stakeholders to be a subset of $\mathbb{D}$ in most cases. That said, we
note a few exceptions in the text that follows.

### Vendors

As shown in Table [6.3](#tab:stakeholder_order){reference-type="ref"
reference="tab:stakeholder_order"}, we expect vendors' desiderata
$\mathbb{D}_v$ to be a subset of $\mathbb{D}$. It seems reasonable to
expect vendors to prefer that a fix is ready before either exploit
publication or attacks ($\mathbf{F} \prec \mathbf{X}$ and
$\mathbf{F} \prec \mathbf{A}$, respectively). Fix availability implies
vendor awareness ($\mathbf{V} \prec \mathbf{F}$), so we would expect
vendors' desiderata to include those orderings as well
($\mathbf{V} \prec \mathbf{X}$ and $\mathbf{V} \prec \mathbf{A}$,
respectively).

Vendors typically want to have a fix ready before the public finds out
about a vulnerability ($\mathbf{F} \prec \mathbf{P}$). We surmise that a
vendor's preference for this item could be driven by at least two
factors: the vendor's tolerance for potentially increased support costs
(e.g., fielding customer support calls while the fix is being prepared),
and the perception that public awareness without an available fix leads
to a higher risk of attacks. As above, vendor preference for
$\mathbf{F} \prec \mathbf{P}$ implies a preference for
$\mathbf{V} \prec \mathbf{P}$ as well.

When a vendor has control over fix deployment ($\mathbf{D}$), it will
likely prefer that deployment precede public awareness, exploit
publication, and attacks ($\mathbf{D} \prec \mathbf{P}$,
$\mathbf{D} \prec \mathbf{X}$, and $\mathbf{D} \prec \mathbf{A}$,
respectively).[^6] However, when fix deployment depends on system owners
to take action, the feasibility of $\mathbf{D} \prec \mathbf{P}$ is
limited.[^7] Regardless of the vendor's ability to deploy fixes or
influence their deployment, it would not be unreasonable for them to
prefer that public awareness precedes both public exploits and attacks
($\mathbf{P} \prec \mathbf{X}$ and $\mathbf{P} \prec \mathbf{A}$,
respectively).

Ensuring the ease of patch deployment by system owners remains a likely
concern for vendors. Conscientious vendors might still prefer
$\mathbf{D} \prec \mathbf{X}$ and $\mathbf{D} \prec \mathbf{A}$ even if
they have no direct control over those factors. However, vendors may be
indifferent to $\mathbf{X} \prec \mathbf{A}$.

Although our model only addresses event ordering, not timing, a few
comments about timing of events are relevant since they reflect the
underlying state transition process from which $\mathcal{H}$ arises.
Vendors have significant influence over the speed of $\mathbf{V}$ to
$\mathbf{F}$ based on their vulnerability handling, remediation, and
development processes [@ISO30111]. They can also influence how early
$\mathbf{V}$ happens based on promoting a cooperative atmosphere with
the security researcher community [@ISO29147]. Vendor architecture and
business decisions affect the speed of $\mathbf{F}$ to $\mathbf{D}$.
Cloud-based services and automated patch delivery can shorten the lag
between $\mathbf{F}$ and $\mathbf{D}$. Vendors that leave deployment
contingent on system owner action can be expected to have longer lags,
making it harder to achieve the $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{D} \prec \mathbf{X}$, and $\mathbf{D} \prec \mathbf{A}$
objectives, respectively.

### System Owners

System owners ultimately determine the lag from $\mathbf{F}$ to
$\mathbf{D}$ based on their processes for system inventory, scanning,
prioritization, patch testing, and deployment---in other words, their
VM practices. In
cases where the vendor and system owner are distinct entities, system
owners should optimize to minimize the lag between $\mathbf{F}$ and
$\mathbf{D}$ in order to improve the chances of meeting the
$\mathbf{D} \prec \mathbf{X}$ and $\mathbf{D} \prec \mathbf{A}$
objectives, respectively. Enabling automatic updates for security
patches is one way to improve $\mathbf{F}$ to $\mathbf{D}$ performance,
although not all system owners find the resulting risk of operational
impact to be acceptable to their change management process.

System owners might select a different desiderata subset than vendors
$\mathbb{D}_s \subseteq \mathbb{D}$, $\mathbb{D}_s \neq \mathbb{D}_v$.
In general, system owners are primarily concerned with the $\mathbf{F}$
and $\mathbf{D}$ events relative to $\mathbf{X}$ and $\mathbf{A}$.
Therefore, we expect system owners to be concerned about
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{X}$, and $\mathbf{D} \prec \mathbf{A}$. As
discussed above, $\mathbf{D} \prec \mathbf{P}$ is only possible when the
vendor controls $\mathbf{D}$. Depending on the system owner's risk
tolerance, $\mathbf{F} \prec \mathbf{P}$ and
$\mathbf{D} \prec \mathbf{X}$ may or may not be preferred. Some system
owners may find $\mathbf{X} \prec \mathbf{A}$ useful for testing their
infrastructure, others might prefer that no public exploits be
available.

### Security Researchers

The "friendly" offensive security community (i.e., those who research
vulnerabilities, report them to vendors, and sometimes release
proof-of-concept exploits for system security evaluation purposes) can
do their part to ensure that vendors are aware of vulnerabilities as
early as possible prior to public disclosure
[\[eq:notify_vendor\]](#eq:notify_vendor){reference-type="eqref"
reference="eq:notify_vendor"}. $$\label{eq:notify_vendor}
vfdpxa \xrightarrow{\mathbf{V}} Vfdpxa \implies \mathbf{V} \prec \mathbf{P} \textrm{, } \mathbf{V} \prec \mathbf{X} \textrm{ and } \mathbf{V} \prec \mathbf{A}$$

Security researchers can also delay the publication of exploits until
after fixes exist [\[eq:fx\]](#eq:fx){reference-type="eqref"
reference="eq:fx"}, are public
[\[eq:fxpx\]](#eq:fxpx){reference-type="eqref" reference="eq:fxpx"}, and
possibly even until most system owners have deployed the fix
[\[eq:fxpxdx\]](#eq:fxpxdx){reference-type="eqref"
reference="eq:fxpxdx"}. $$\begin{aligned}
\label{eq:fx}
  \mathbf{X}|q \in VFdpx &\implies \mathbf{F} \prec \mathbf{X} \\
  \label{eq:fxpx}
  \mathbf{X}|q \in VFdPx &\implies \mathbf{F} \prec \mathbf{X} \textrm{ and } \mathbf{P} \prec \mathbf{X}\\
  \label{eq:fxpxdx}
  \mathbf{X} |q \in VFDPx &\implies \mathbf{F} \prec \mathbf{X} \textrm{, } \mathbf{P} \prec \mathbf{X} \textrm{ and } \mathbf{D} \prec \mathbf{X} 
\end{aligned}$$ This does not preclude adversaries from doing their own
exploit development on the way to $\mathbf{A}$, but it avoids providing
them with unnecessary assistance.

### Coordinators

Coordinators have been characterized as seeking to balance the social
good across both vendors and system owners [@arora2008optimal]. This
implies that they are likely interested in the union of the vendors' and
system owners' preferences. In other words, coordinators want the full
set of desiderata ($\mathbb{D}_c = \mathbb{D}$).

We pause for a brief aside about the design of the model with respect to
the coordination role. We considered adding a *Coordinator Awareness*
($\mathbf{C}$) event, but this would expand $|\mathcal{H}|$ from 70 to
452 because it could occur at any point in any $h$. There is not much
for a coordinator to do once the fix is deployed, however, so we could
potentially reduce $|\mathcal{H}|$ to 329 by only including positions in
$\mathcal{H}$ that precede the $\mathbf{D}$ event. This is still too
large and unwieldy for meaningful analysis within our scope; instead, we
simply provide the following comment.

The goal of coordination is this: regardless of which stage a
coordinator becomes involved in a case, the objective is to choose
actions that make preferred histories more likely and non-preferred
histories less likely.

The rules outlined in §[6.8](#sec:cvd_action_rules){reference-type="ref"
reference="sec:cvd_action_rules"} suggest available actions to improve
outcomes. Namely, this means focusing coordination efforts as needed on
vendor awareness, fix availability, fix deployment, and the
appropriately timed public awareness of vulnerabilities and their
exploits ($\mathbf{V}$,$\mathbf{F}$,$\mathbf{D}$, $\mathbf{P}$, and
$\mathbf{X}$).

### Governments

In their defensive roles, governments act as a combination of system
owners, vendors, andincreasinglycoordinators. Therefore we might
anticipate $\mathbb{D}_g = \mathbb{D}_c = \mathbb{D}$.

However, governments sometimes also have an adversarial role to play for
national security, law enforcement, or other reasons. The model
presented in this paper could be adapted to that role by drawing some
desiderata from the lower left triangle of Table
[3.3](#tab:ordered_pairs){reference-type="ref"
reference="tab:ordered_pairs"}. While defining such adversarial
desiderata ($\mathbb{D}_a$) is out of scope for this paper, we leave the
topic with our expectation that $\mathbb{D}_a \not\subseteq \mathbb{D}$.

## Disclosure Policy Formalization {#sec:policy_formalism}

In this section, we apply our model to the formalization of
vulnerability disclosure policies. This discussion is not intended to be
a complete formalization of all possible policy choices; rather, we seek
to relate how some aspects of disclosure policies might be formalized
using our model. In particular, we will look at applications of the
model to embargoes and service level expectations.

### Embargo Initiation Policies

An agreement between coordinating stakeholders to keep information about
the vulnerability private until some exit condition has been met is
called an *embargo*.[^8] Examples of exit conditions for
CVD embargoes
include the expiration of a timer or a the occurrence of a triggering
event such as fix availability. The model gives us a way of formally
specifying the conditions under which initiating or maintaining an
embargo may or may not be appropriate.

Let us first examine which states are eligible for embargoes to be
initiated. The whole point of an embargo is to restrict public knowledge
of the vulnerability for some period of time, corresponding to a desire
to avoid entering $\mathcal{Q}_{P}$ until the embargo ends. Therefore,
it follows that our set of embargo initiation states must reside in
$\mathcal{Q}_{p}$. Furthermore, as we have discussed, $pX$ is inherently
unstable because publication of an exploit necessarily leads to public
awareness of the vulnerability. Because $pX$ leads immediately to $PX$,
we can infer that our embargo entry points must be in $px$.

Many disclosure policies---including CERT/CC's---eschew embargoes when attacks are
underway ($\mathcal{Q}_{A}$). This implies we should be looking in
$pxa$. We further observe that there is little reason to initiate an
information embargo about a vulnerability after the fix has been
deployed[^9] ($D$) and thus continue with $dpxa$.

In cases where a single vendor and product are affected, then fix
readiness is truly binary (it either is or is not ready), and there may
be no need to enter into an embargo when the fix is ready (i.e., in
$Fdpxa$). However, while may be tempted to expand the requirement and
narrow the states of interest to $fdpxa$, we must allow for the
multiparty situation in which some vendors have a fix ready ($Fp$) while
others do not ($fp$). We discuss MPCVD further in section
§[6.2](#sec:mpcvd){reference-type="ref" reference="sec:mpcvd"}. Here we
note that in MPCVD cases, prudence requires us to allow for
a (hopefully brief) embargo period to enable more vendors to achieve
$fp \xrightarrow{\mathbf{F}} Fp$ prior to public disclosure
($\mathbf{F} \prec \mathbf{P}$). Therefore we stick with $dpxa$ for the
moment.

Finally, because embargoes are typically an agreement between the vendor
and other coordinating parties, it might appear that we should expect
embargoes to begin in ${Vdpxa}$. However, doing so would neglect the
possibility of embargoes entered into by finders, reporters, and
coordinators prior to vendor awareness---i.e., in ${vfdpxa}$. In fact,
the very concept of CVD is built on the premise that every newly
discovered vulnerability should have a default embargo at least until
the vendor has been informed about the vulnerability (i.e.,
${vfdpxa} \xrightarrow{\mathbf{V}} {Vfdpxa}$ is
CVD's preferred
initial state transition). And so, having considered all possible
states, we conclude that embargoes can only begin from ${dpxa}$, with
the caveat that practitioners should carefully consider why they would
enter an embargo from ${Fdpxa}$.

This leaves us with only few states from which we can enter an embargo,
which we denote as $\mathcal{Q}_{E}^{0}$:

$$\label{eq:embargo_start}
    \mathcal{Q}_{E}^{0} \stackrel{\mathsf{def}}{=}{dpxa} = \{{vfdpxa}, {Vfdpxa}, {VFdpxa}\}$$

### Embargo Continuation Policies

Having shown the limited number of states from which an embargo can
begin, we turn next to the states in which an embargo remains viable. By
*viable* we mean that maintaining the embargo is reasonable and not
contraindicated by the facts at hand. It is of course possible for
parties to attempt to maintain embargoes in spite of facts indicating
they should do otherwise. We are not here to support such contrived
arguments.

By definition an embargo must be viable in all the states it can start
from, so we'll begin with $\mathcal{Q}_{E}^{0}$ (${dpxa}$) and consider
which restrictions we can relax, as there may be states in which an
existing embargo remains viable even if one should not initiate a new
one.

To begin, states in $\mathcal{Q}_{p}$ remain a necessary condition
because keeping the public from becoming aware of the vulnerability too
early is the key state the embargo is intended to maintain. Furthermore,
because our starting criteria is already indifferent to vendor awareness
and fix availability, we will not revisit those here.

It appears we can relax $\mathcal{Q}_{d}$ because it is certainly
possible in some situations to maintain an embargo after a fix is
deployed, as is common in CVD cases regarding specific instances of
vulnerabilities. For example, web site vulnerabilities are often only
published after the system is no longer vulnerable. So our set of viable
states is currently ${pxa}$.

Next, we address two potential sticking points, $\mathbf{X}$ and
$\mathbf{A}$. First, how long can an existing embargo persist in ${pX}$?
The embargo can persist only for as long as it takes for public
awareness of its existence to take hold
${pX} \xrightarrow{\mathbf{P}} {PX}$. This might be reasonable for a few
hours or at best a few days, but not much longer.[^10] In other words,
an active embargo for a vulnerability case in a state $q \in {pX}$ has
either already failed or is at imminent risk of failure to prevent
public awareness. For this reason, it seems better to presume embargo
non-viability in ${pX}$.

Second, what should we do if an embargo is in place and we find out that
attacks are happening---i.e., we assess that we are in a state
$q \in {pA}$? Cases in ${pA}$ give the attacker an advantage over
defenders insofar as attackers are able to exploit vulnerabilities while
deployers remain ignorant of steps they might take to defend their
systems. For this reason, many organizations' disclosure policies
explicitly call out observed attacks as a reason to break an embargo.
Therefore, while it may be technically possible to maintain an embargo
in ${pxA}$, we remain skeptical of the reason for doing so, if not to
maintain the ability for attacks to remain stealthy.

In the interest of avoiding justification for bad faith disclosure
behaviors, we hold that embargoes remain viable only in ${pxa}$, with
the caveat that only limited circumstances as described above justify
maintaining embargoes once $\mathbf{F}$ or $\mathbf{D}$ have occurred
(${VFdpxa}$ and ${VFDpxa}$, respectively).

$$\label{eq:embargo_viable}
    \mathcal{Q}_{E} \stackrel{\mathsf{def}}{=}{pxa} = \{{vfdpxa}, {Vfdpxa}, {VFdpxa}, {VFDpxa}\}$$

In summary, embargoes can be initiated if the case is in
$\mathcal{Q}_{E}^{0}$ as in Eq.
[\[eq:embargo_start\]](#eq:embargo_start){reference-type="eqref"
reference="eq:embargo_start"}, and remain viable through any state in
$\mathcal{Q}_{E}$ as in Eq.
[\[eq:embargo_viable\]](#eq:embargo_viable){reference-type="eqref"
reference="eq:embargo_viable"}. This in turn gives us specific things to
look for in order to determine when to end an embargo:

-   The embargo timer has expired.

-   Any observation of $\mathbf{P}$, $\mathbf{X}$, or $\mathbf{A}$ has
    been made ($q \not\in {pxa}$).

-   $\mathbf{F}$ or $\mathbf{D}$ have occurred
    ($q \in \{{VFdpxa}, {VFDpxa}\})$, and no reasons specific to the
    case to maintain the embargo remain.

-   Any other embargo exit rules---such as those specified in the
    relevant disclosure policies---have been triggered.

### CVD Service Level Expectations

Closely related to CVD embargoes are CVD SLEs. Disclosure policies specify commitments by
coordinating parties to ensure the occurrence of certain state
transitions within a specific period of time. While the model presented
here does not directly address timing choices, we can point out some
ways to relate the model to those choices. Specifically, we intend to
demonstrate how disclosure policy SLEs can be stated as rules triggered within
subsets of states or by particular transitions between subsets of states
in $\mathcal{Q}$.

For example, a finder, reporter, or coordinator might commit to
publishing information about a vulnerability 30 days after vendor
notification. This translates to starting a timer at
${v} \xrightarrow{\mathbf{V}} {V}$ and ensuring
${Vp} \xrightarrow{\mathbf{P}} {VP}$ when the timer expires. Notice that
the prospect of ${Vfp} \xrightarrow{\mathbf{P}} {VfP}$ is often used to
motivate vendors to ensure a reasonable SLE to produce fixes
(${Vf} \xrightarrow{\mathbf{F}} {VF}$) [@arora2008optimal].

Similarly, a vendor might commit to providing public fixes within 5
business days of report receipt. In that case, the
SLE timer would
start at ${vfp} \xrightarrow{\mathbf{V}} {Vfp}$ and and end at one of
two transitions: First, the "normal" situation in which the vendor
creates a fix and makes it public along with the vulnerability
($\mathbf{F} \prec \mathbf{P}$, i.e.,
${VFp} \xrightarrow{\mathbf{P}} {VFP}$). Second, a "zero day"
situation[^11] in which events outside the vendor's control cause the
${Vfp} \xrightarrow{\mathbf{P}} {VfP}$ transition to occur prior to the
fix being ready (${VfP} \xrightarrow{\mathbf{F}} {VFP}$), i.e,
$\mathbf{P} \prec \mathbf{F}$. Likewise, the
${Vfp} \xrightarrow{\mathbf{P}} {VfP} \xrightarrow{\mathbf{F}} {VFP}$
path might also occur when a vendor has set their embargo timer too
aggressively for their development process to keep up.

It is therefore in the vendor's interest to tune their
SLE to reduce the
likelihood for unexpected public awareness ($\mathbf{P}$) while
providing sufficient time for $\mathbf{F}$ to occur, optimizing to
achieve $\mathbf{F} \prec \mathbf{P}$ in a substantial fraction of
cases. As future work, measurement of both the incidence and timing of
embargo failures through observation of $\mathbf{P}$, $\mathbf{X}$, and
$\mathbf{A}$ originating from $\mathcal{Q}_{E}$ could give insight into
appropriate vendor SLEs for fix readiness ($\mathbf{F}$).

Service providers and VM practitioners might similarly describe
their SLEs in terms
of timing between states. Such policies will likely take the form of
commitments to limit the time spent in ${FdP}$. When the vendor has
already produced a patch, the clock starts at
${Fdp} \xrightarrow{\mathbf{P}} {FdP}$, whereas if the vulnerability
becomes public prior to patch the clock starts at
${fdP} \xrightarrow{\mathbf{F}} {FdP}$. In both cases, the timer ends at
${FdP} \xrightarrow{\mathbf{D}} {FDP}$.

Future formal definitions of policy statements might take the general
form of specifications including

-   Starting state ($q \in \mathcal{Q}$) or subset of states
    ($S \subset \mathcal{Q}$)

-   Expected transitions ($\sigma \in \Sigma$) and
    SLEs around their
    timing, including possible constraints such as "not before" and "no
    later than" specifications

-   An indication of constraint rigidity (negotiable, fixed, *MUST*,
    *SHOULD*, *MAY* [@bradner1997rfc2119], etc.)

-   Potential exceptions in the form of other transitions
    ($\sigma \in \Sigma$) that might alter expected behavior, and a
    description of the anticipated response.

One reason to formalize policy definitions is the potential to
automatically resolve embargo negotiations when those policies are
compatible. It may be possible to resolve some apparent policy conflicts
by delaying notifications to some vendors to ensure that all embargo end
timers expire simultaneously. We informally refer to this as the
*Thanksgiving Dinner problem*, due to its similarity to the familiar
annual holiday meal in which a number of dishes with varying preparation
times are expected to be delivered to the table simultaneously, each at
its appropriate temperature and doneness. For example, when one party
has a "minimum 90 days to publish" policy and another has a "maximum 5
days to publish" policy, the resolution could be to notify the first
vendor 85 days before notifying the second. Such a model of graduated
disclosure could work well for cases where notifications are automated
and vendor dependencies are small or where coordinating parties'
policies can be resolved as compatible. Technology such as Theorem
Provers and Solvers seem likely to be suited to this sort of problem.

However, when formal policies are incompatible, the failure to resolve
them automatically becomes an opportunity for human intervention as the
exception handler of last resort. Of potential concern here are
MPCVD cases in
which a vendor with a long policy timer is dependent on one with a short
policy timer to provide fixes. The serial nature of the dependency
creates the potential for a compatibility conflict. For example, this
can happen when an OS kernel provider's disclosure policy specifies a
shorter embargo timer than the policies of device manufacturers whose
products depend on that OS kernel. Automation can draw attention to
these sorts of conflicts, but their resolution is likely to require
human intervention for some time to come.

## Improving Definitions of Common Terms {#sec:defining_common_terms}

Some terms surrounding CVD and VM have been ambiguously defined in common
usage. One benefit of the definition of events, states, and possible CVD
histories presented in this whitepaper is an opportunity to clarify
definitions of related terms. In this section we will use our model to
formally define their meaning.

### Zero Day {#sec:zerodays}

The information security community uses a variety of common phrases that
contain the words *zero day*. This creates confusion. For example, a
reviewer stated that they prefer to define "zero day vulnerability" as
$\mathbf{X} \prec \mathbf{V}$ and not $(\mathbf{P} \prec \mathbf{F}$ or
$\mathbf{A} \prec \mathbf{F})$. We should seek these precise definitions
because sometimes both $\mathbf{X} \prec \mathbf{V}$ and
$\mathbf{P} \prec \mathbf{F}$ are true, in which case two people might
agree that an instance is a "zero day" without realizing that they
disagree on its definition. We can resolve these formally using our
model. This section extends prior work by one of the authors in
[@householder2015zeroday].

zero day vulnerability

:   Two common definitions for this term are in widespread use; a third
    is drawn from an important policy context. The two commonly-used
    definitions can be considered a relatively *low* threat level
    because they only involve states $q \in {xa}$ where no exploits are
    public and no attacks have occurred. We ordered all three
    definitions in approximately descending risk due to the expected
    duration until $\mathbf{D}$ can be achieved.

    1.  $q \in vp$ The United States VEP [@usg2017vep] defines *zero day
        vulnerability* in a manner consistent with $q \in {vp}$. Further
        discussion appears in §[6.7](#sec:vep){reference-type="ref"
        reference="sec:vep"}.

    2.  ${vp} \xrightarrow{\mathbf{P}} {vP}$ when the vulnerability
        becomes public before the vendor is aware of it. Note that our
        model assumes that states in ${vP}$ are unstable and resolve to
        ${vP} \xrightarrow{\mathbf{V}} {VP}$ in the next step.

    3.  ${fp} \xrightarrow{\mathbf{P}} {fP}$ when the vulnerability
        becomes public before a fix is available, regardless of the
        vendor's awareness. Some states in ${fP}$---specifically, those
        in ${VfP}$---are closer to ${\mathbf{F}}$ (and therefore
        ${\mathbf{D}}$) occuring than others (i.e., ${vfP}$), thus this
        definition could imply less time spent at risk than the first.

zero day exploit

:   This term has three common definitions. Each can be considered a
    *moderate* threat level because they involve transition from
    ${xa} \xrightarrow{\mathbf{X}} {Xa}$. However, we ordered them in
    approximately descending risk due to the expected duration until
    $\mathbf{D}$ can be achieved.

    1.  ${vfdx} \xrightarrow{\mathbf{X}} {vfdX}$ when an exploit is
        released before the vendor is aware of the vulnerability.

    2.  ${fdx} \xrightarrow{\mathbf{X}} {fdX}$ when an exploit is
        released before a fix is available for the vulnerability.
        Because $\mathcal{Q}_{vf} \subset \mathcal{Q}_{f}$, any scenario
        matching the previous definition also matches this one.

    3.  ${px} \xrightarrow{\mathbf{X}} {pX}$ when an exploit is released
        before the public is aware of the vulnerability. Note that our
        model assumes that states in ${pX}$ are unstable and transition
        ${pX} \xrightarrow{\mathbf{P}} {PX}$ in the next step.

zero day attack

:   We have identified three common definitions of this term. Each can
    be considered a *high* threat level because they involve the
    $\mathbf{A}$ transition. However, we ordered them in approximately
    descending risk due to the expected duration until $\mathbf{D}$ can
    be achieved.

    1.  ${vfda} \xrightarrow{\mathbf{A}} {vfdA}$ when attacks against
        the vulnerability occur before the vendor is aware of the
        vulnerability.

    2.  ${fda} \xrightarrow{\mathbf{A}} {fdA}$ when attacks against the
        vulnerability occur before a fix is available for the
        vulnerability. As with *zero day exploit*, because
        $\mathcal{Q}_{vf} \subset \mathcal{Q}_{f}$, any scenario
        matching the previous definition also matches this one.

    3.  ${pa} \xrightarrow{\mathbf{A}} {pA}$ when attacks against the
        vulnerability occur before the public is aware of the
        vulnerability. Note that this definition disregards the vendor
        entirely since it makes no reference to either $\mathbf{V}$ or
        $\mathbf{F}$.

### Forever Day

In common usage, a *forever day* vulnerability is one that is expected
to remain unpatched indefinitely [@ars2012forever]. In other words, the
vulnerability is expected to remain in $d$ forever. This situation can
occur when deployed code is abandoned for a number of reasons,
including:

1.  The vendor has designated the product as EoL and thereby declines to fix any
    further security flaws, usually implying $q \in {Vfd}$. Vendors
    should evaluate their support posture for EoL products when they are aware of
    vulnerabilities in ${VfdX}$ or ${VfdA}$. Potential vendor responses
    include issuing additional guidance or an out-of-support patch.

2.  The vendor no longer exists, implying a state $q \in {vfd}$. Neither
    $\mathbf{F}$ nor $\mathbf{D}$ transitions can be expected although
    $\mathbf{P}$, $\mathbf{X}$, and $\mathbf{A}$ remain possible. For
    this reason alone, coordinators or other stakeholders may choose to
    publish anyway to cause $\mathbf{P}$. In this situation, if
    deployers are to respond at all, states in ${vfdP}$ are preferable
    to states in ${vfdp}$. Defender options in this case are usually
    limited to retiring or otherwise isolating affected systems,
    especially for vulnerabilities in either ${vfdPX}$ or ${vfdPA}$.

3.  The deployer chooses to never deploy, implying an expectation to
    remain in ${d}$ until the affected systems are retired or otherwise
    removed from service. This situation may be more common in
    deployments of safety-critical systems and OT than it is in IT deployments. It is also the most
    reversible of the three *forever day* scenarios, because the
    deployer can always reverse their decision as long as a fix is
    available ($q \in {VF}$). In deployment environments where other
    mitigations are in place and judged to be adequate, and where the
    risk posed by $\mathbf{X}$ and/or $\mathbf{A}$ are perceived to be
    low, this can be a reasonable strategy within a
    VM program.

Scenarios in which the vendor has chosen not to develop a patch for an
otherwise supported product, and which also imply $q \in {Vfd}$, are
omitted from the above definition because as long as the vendor exists
the choice to not develop a fix remains reversible. That said, such
scenarios most closely follow the first bullet in the list above.

## Vulnerability Response Situation Awareness {#sec:situation_awareness}

In this section, we demonstrate how the model can be applied to improve
situation awareness for coordinating parties and other stakeholders.

##### SSVC v2.0 {#sec:ssvc}

::: {#tab:ssvc_v2_states}
       States       SSVC Decision Point            SSVC Value
  ---------------- --------------------- ------------------------------
        $xa$           Exploitation                   None
        $Xa$           Exploitation          PoC (Proof of Concept)
        $A$            Exploitation                  Active
        $p$            Report Public                   No
        $P$            Report Public                  Yes
        $V$         Supplier Contacted                Yes
        $v$         Supplier Contacted    No (but see text for caveat)
        $p$         Public Value Added             Precedence
   $VFdp$ or $dP$   Public Value Added             Ampliative
       $VFP$        Public Value Added              Limited

  : Mapping Subsets of States $\mathcal{Q}$ to SSVC v2.0
:::

Vulnerability prioritization schemes such as SSVC
[@spring2019ssvc; @spring2020ssvc; @spring2021ssvc] generally give
increased priority to states in higher threat levels, corresponding to
$q \in \mathcal{Q}_X \cup \mathcal{Q}_A$. SSVC also includes decision
points surrounding other states in our model. A summary of the relevant
SSVC decision points and their intersection with our model is given in
Table [6.4](#tab:ssvc_v2_states){reference-type="ref"
reference="tab:ssvc_v2_states"}.

Not all SSVC decision point values map as clearly onto states in this
model however. For example, *Supplier Contacted=No* likely means
$q \in \mathcal{Q}_{v}$ but it is possible that the vendor has found out
another way, so one cannot rule out $q \in \mathcal{Q}_{V}$ on this
basis alone. However, notifying the vendor yourself forces you into
$q \in \mathcal{Q}_{V}$. Therefore it is always in the coordinator's
interest to encourage, facilitate, or otherwise cause the vendor to be
notified.

Other SSVC decision points may be informative about which transitions to
expect in a case. Two examples apply here: First, *Supplier Engagement*
acts to gauge the likelihood of the $\mathbf{F}$ transitions.
Coordination becomes more necessary the lower that likelihood is.
Second, *Utility* (the usefulness of the exploit to the adversary) acts
to gauge the likelihood of the $\mathbf{A}$ transition.

##### Mapping to CVSS v3.1 {#sec:cvss}

CVSS version 3.1
includes a few Temporal Metric variables that connect to this model
[@first2019cvss31]. Unfortunately, differences in abstraction between
the models leaves a good deal of ambiguity in the translation. Table
[6.5](#tab:cvss_31){reference-type="ref" reference="tab:cvss_31"} shows
the relationship between the two models.

::: {#tab:cvss_31}
   States   CVSS v3.1 Temporal Metric  CVSS v3.1 Temporal Metric Value(s)
  -------- --------------------------------------------------------------------------------- ------------------------------------------------------------------------------------------
   ${XA}$                                  Exploit Maturity                                  High (H), or Functional (F)
   ${X}$                                   Exploit Maturity                                  High (H), Functional (F), or Proof-of-Concept (P)
   ${x}$                                   Exploit Maturity                                  Unproven (U) or Not Defined (X)
   ${Vf}$                                  Remediation Level                                 Not Defined (X), Unavailable (U), Workaround (W), or Temporary Fix (T)
   ${VF}$                                  Remediation Level                                 Temporary Fix (T) or Official Fix (O)

  : Mapping Subsets of States $\mathcal{Q}$ to
  CVSS v3.1
:::

##### Addressing Uncertainty in Situation Awareness

It is possible to use this model to infer what other decisions can be
made based on incomplete information about a case. For example, imagine
that a vendor just found out about a vulnerability in a product and has
taken no action yet. We know they are in ${Vf}$, but that leaves 8
possible states for the case to be in: $$\begin{aligned}
    {Vf} = \{ & {Vfdpxa}, {VfdPxa}, {VfdpXa}, \\ 
              & {VfdpxA}, {VfdPXa}, {VfdpXA}, \\
              & {VfdPxA}, {VfdPXA} \}
\end{aligned}$$

Can we do better than simply assigning equal likelihood
$p(q|Vf) = 0.125$ to each of these states? Yes: we can use the PageRank
computations from Table
[3.4](#tab:allowed_state_transitions){reference-type="ref"
reference="tab:allowed_state_transitions"} to inform our estimates.

To assess our presence in ${Vf}$, we can select just the subset of
states we are interested in. But our PageRank values are computed across
all 32 states and we are only interested in the relative probabilities
within a subset of 8 states. Thus, we normalize the PageRank for the
subset to find the results shown in Table
[6.6](#tab:pagerank_vf){reference-type="ref"
reference="tab:pagerank_vf"}. As a result, we find that the most likely
state in ${Vf}$ is ${VfdPXA}$ with probability $0.24$, nearly twice what
we would have expected ($1/8 = 0.125$) if we just assumed each state was
equally probable.

::: {#tab:pagerank_vf}
    State     PageRank   Normalized
  ---------- ---------- ------------
   $VfdPXA$    0.063       0.245
   $VfdPXa$    0.051       0.200
   $VfdPxa$    0.037       0.146
   $VfdPxA$    0.032       0.126
   $Vfdpxa$    0.031       0.120
   $VfdpxA$    0.020       0.078
   $VfdpXa$    0.011       0.044
   $VfdpXA$    0.010       0.040

  : PageRank and normalized state probabilities for states in ${Vf}$
:::

## VEP {#sec:vep}

The VEP is the
United States government's process to decide whether to inform vendors
about vulnerabilities they have discovered. The
VEP Charter
[@usg2017vep] describes the process:

> The Vulnerabilities Equities Process (VEP) balances whether to
> disseminate vulnerability information to the vendor/supplier in the
> expectation that it will be patched, or to temporarily restrict the
> knowledge of the vulnerability to the USG, and potentially other
> partners, so that it can be used for national security and law
> enforcement purposes, such as intelligence collection, military
> operations, and/or counterintelligence.

For each vulnerability that enters the process, the
VEP results in a
decision to *disseminate* or *restrict* the information.

In terms of our model:

disseminate

:   is a decision to notify the vendor, thereby triggering the
    transition
    $\mathcal{Q}_{v} \xrightarrow{\mathbf{V}} \mathcal{Q}_{V}$.

restrict

:   is a decision not to notify the vendor and remain in
    $\mathcal{Q}_{v}$.

VEP policy does not
explicitly touch on any other aspect of the CVD process. By solely addressing
$\mathbf{V}$, VEP
is mute regarding intentionally triggering the $\mathbf{P}$ or
$\mathbf{X}$ transitions. It also makes no commitments about
$\mathbf{F}$ or $\mathbf{D}$, although obviously these are entirely
dependent on $\mathbf{V}$ having occurred. However, preserving the
opportunity to exploit the vulnerability implies a chance that such use
would be observed by others, thereby resulting in the $\mathbf{A}$
transition.

The charter sets the following scope requirement as to which
vulnerabilities are eligible for VEP:

> To enter the process, a *vulnerability* must be both *newly
> discovered* and not *publicly known*

given the following definitions (from Annex A of [@usg2017vep])

Newly Discovered

:   After February 16, 2010, the effective date of the initial
    Vulnerabilities Equities Process, when the USG discovers a zero-day
    vulnerability or new zero-day vulnerability information, it will be
    considered newly discovered. This definition does NOT preclude entry
    of vulnerability information discovered prior to February 16, 2010.

Publicly known

:   A vulnerability is considered publicly known if the vendor is aware
    of its existence and/or vulnerability information can be found in
    the public domain (e.g., published documentation, Internet, trade
    journals).

Vulnerability

:   A weakness in an information system or its components (e.g., system
    security procedures, hardware design, internal controls) that could
    be exploited or impact confidentiality, integrity, or availability
    of information.

Zero-Day Vulnerability

:   A type of vulnerability that is unknown to the vendor, exploitable,
    and not publicly known.

Mapping back to our model, the VEP definition of *newly discovered* hinges
on the definition of *zero day vulnerability*. The policy is not clear
what distinction is intended by the use of the term *exploitable* in the
*zero day vulnerability* definition, as the definition of
*vulnerability* includes the phrase "could be exploited,\" seeming to
imply that a non-exploitable vulnerability might fail to qualify as a
*vulnerability* altogether. Regardless, "unknown to the vendor" clearly
matches with $\mathcal{Q}_{v}$, and "not publicly known" likewise
matches with $\mathcal{Q}_{p}$. Thus we interpret their definition of
*newly discovered* to be consistent with $q \in {vp}$.

VEP's definition of
*publicly known* similarly specifies either "vendor is aware"
($\mathcal{Q}_{V}$) or "information can be found in the public domain"
($\mathcal{Q}_{P}$). As above, the logical negation of these two
criteria puts us back in $q \in {vp}$ since
${vp} = \lnot \mathcal{Q}_{V} \cap \lnot \mathcal{Q}_{P}$. We further
note that because a public exploit ($\mathcal{Q}_X$) would also meet the
definition of "vulnerability information in the public domain," we can
narrow the scope from ${vp}$ to ${vpx}$. Lastly, we note that due to the
vendor fix path causality rule in Eq.
[\[eq:history_vfd_rule\]](#eq:history_vfd_rule){reference-type="eqref"
reference="eq:history_vfd_rule"}, ${vpx}$ is equivalent to ${vfdpx}$,
and therefore we can formally specify that VEP is only applicable to vulnerabilities in

$$\mathcal{S}_{VEP} = {vfdpx} = \{vfdpxa, vfdpxA\}$$

Vulnerabilities in any other state by definition should not enter into
the VEP, as the
first transition from ${vfdpx}$ (i.e., $\mathbf{V}$, $\mathbf{P}$, or
$\mathbf{X}$) exits the inclusion criteria. However it is worth
mentioning that the utility of a vulnerability for offensive use
continues throughout $\mathcal{Q}_d$, which is a considerably larger
subset of states than ${vfdpx}$ ($|\mathcal{Q}_d| = 24$,
$|\mathcal{Q}_{vfdpx}| = 2$).

## Recommended Action Rules for CVD {#sec:cvd_action_rules}

Another application of this model is to recommend actions for
coordinating parties in CVD based on the subset of states that
currently apply to a case. What a coordinating party does depends on
their role and where they engage, as shown in the list below. As
described in §[6.2](#sec:mpcvd){reference-type="ref"
reference="sec:mpcvd"}, MPCVD attempts to synchronize state transitions
across vendors.

A significant portion of CVD can be formally described as a set of
action rules based on this model. For our purposes, a
CVD action rule
consists of:

State subset

:   The subset of states $Q \in \mathcal{Q}$ from which the action may
    be taken

Role(s)

:   The role(s) capable of performing the action

Action

:   A summary of the action to be taken

Reason

:   The rationale for taking the action

Transition

:   The state transition event $\sigma \in \Sigma$ induced by the action
    (if any)

This rule structure follows a common user story pattern:

> When a case is in a state $q \in Q \subseteq \mathcal{Q}$, a *Role*
> can do *Action* for *Reason*, resulting in the transition event
> $\sigma \in \Sigma$

The list in Table [6.7](#tab:cvd_rules){reference-type="ref"
reference="tab:cvd_rules"} can be built into a rules engine that
translates each state in the model to a set of suggested
CVD actions.

::: {#tab:cvd_rules}
        State Subset       Role(s)            Action                                                       Reason                                            $\sigma$
  ------------------------ ------------------ ------------------------------------------------------------ ---------------------------------------------- --------------
   Continued on next page                                                                                                                                 
            $P$            any                Terminate any existing embargo                               Exit criteria met                                    \-
            $X$            any                Terminate any existing embargo                               Exit criteria met                                    \-
            $A$            any                Terminate any existing embargo                               Exit criteria met                                    \-
            $x$            any                Monitor for exploit publication                              SA                                                   \-
            $X$            any                Monitor for exploit refinement                               SA                                                   \-
            $a$            any                Monitor for attacks                                          SA                                                   \-
            $A$            any                Monitor for additional attacks                               SA                                                   \-
           $vfdP$          vendor             Pay attention to public reports                              SA                                              $\mathbf{V}$
            $pX$           any                Draw attention to published exploit(s)                       SA                                              $\mathbf{P}$
            $PX$           any                Draw attention to published exploit(s)                       SA                                              $\mathbf{P}$
           $pxa$           any                Maintain vigilance for embargo exit criteria                 SA                                                   \-
           $VfdP$          any                Escalate vigilance for exploit publication or attacks        SA, Coordination                                     \-
            $X$            any                Publish detection(s) for exploits                            Detection                                       $\mathbf{P}$
            $A$            any                Publish detection(s) for attacks                             Detection                                       $\mathbf{P}$
            $Vp$           any                Publish vul and any mitigations (if no active embargo)       Defense                                         $\mathbf{P}$
           $fdP$           any                Publish mitigations                                          Defense                                              \-
            $pX$           any                Publish vul and any mitigations                              Defense                                         $\mathbf{P}$
            $PX$           any                Publish vul and any mitigations                              Defense                                         $\mathbf{P}$
            $pA$           any                Publish vul and any mitigations                              Defense                                         $\mathbf{P}$
           $VfdP$          any                Publish mitigations                                          Defense                                              \-
           $vfdp$          any                Publish vul and any mitigations (if no vendor exists)        Defense                                         $\mathbf{P}$
           $VfdP$          any                Ensure any available mitigations are publicized              Defense                                              \-
           $Vfd$           vendor             Create fix                                                   Defense                                         $\mathbf{F}$
           $VFdp$          vendor, deployer   Deploy fix (if possible)                                     Defense                                         $\mathbf{D}$
           $VFdP$          deployer           Deploy fix                                                   Defense                                         $\mathbf{D}$
          $fdPxA$          any                Publish exploit code                                         Defense, Detection                              $\mathbf{X}$
          $VFdPxa$         any                Publish exploit code                                         Defense, Detection, Accelerate deployment       $\mathbf{X}$
           $vfd$           non-vendor         Notify vendor                                                Coordination                                    $\mathbf{V}$
            $dP$           any                Escalate response priority among responding parties          Coordination                                         \-
            $dX$           any                Escalate response priority among responding parties          Coordination                                         \-
            $dA$           any                Escalate response priority among responding parties          Coordination                                         \-
           $Vfd$           non-vendor         Encourage vendor to create fix                               Coordination                                         \-
           $pxa$           any                Maintain any existing disclosure embargo                     Coordination                                         \-
           $dpxa$          any                Negotiate or establish disclosure embargo                    Coordination                                         \-
           $VfdP$          non-vendor         Escalate fix priority with vendor                            Coordination                                         \-
           $Vfdp$          non-vendor         Publish vul                                                  Coordination, Motivate vendor to fix            $\mathbf{P}$
           $Vfdp$          any                Publish vul                                                  Coordination, Motivate deployers to mitigate    $\mathbf{P}$
           $VFdp$          non-vendor         Encourage vendor to deploy fix (if possible)                 Coordination                                         \-
          $VFdpxa$         any                Scrutinize appropriateness of initiating a new embargo       Coordination                                         \-
           $VFdp$          any                Publish vul and fix details                                  Accelerate deployment                           $\mathbf{P}$
           $VFdP$          any                Promote fix deployment                                       Accelerate deployment                                \-
           $VFDp$          any                Publish vulnerability                                        Document for future reference                   $\mathbf{P}$
           $VFDp$          any                Publish vulnerability                                        Acknowledge contributions                       $\mathbf{P}$
           $fdxa$          any                Discourage exploit publication until at least $\mathbf{F}$   Limit attacker advantage                             \-
          $vfdpx$          US Gov't           Initiate VEP (if applicable)                                 Policy                                               \-
          $VFDPXA$         any                Close case                                                   No action required                                   \-
          $VFDPxa$         any                Close case (unless monitoring for X or A)                    No action required                                   \-
          $VFDPXa$         any                Close case (unless monitoring for A)                         No action required                                   \-
          $VFDPxA$         any                Close case (unless monitoring for X)                         No action required                                   \-

  : CVD Action
  Rules based on States
:::

