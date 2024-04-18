# Measuring and Benchmarking MPCVD

Multiparty Coordinated Vulnerability Disclosure (MPCVD) is the
process of coordinating the creation, release, publication, and
potentially the deployment of fixes for vulnerabilities across a number
of vendors and their respective products. The need for
MPCVD arises due
to the inherent nature of the software supply chain
[CERT Guide to CVD](https://certcc.github.io/CERT-Guide-to-CVD). A vulnerability that affects a low-level
component (such as a library or operating system API) can require fixes
from both the originating vendor and any vendor whose products
incorporate the affected component. Alternatively, vulnerabilities are
sometimes found in protocol specifications or other design-time issues
where multiple vendors may have each implemented their own components
based on a vulnerable design.

## State Tracking in MPCVD

Applying our [state-based model](../process_models/cs/index.md)
to MPCVD requires a forking approach to the state tracking.

!!! example "MPCVD Case State Tracking"

    At the time of discovery, the vulnerability is in state
    $vfdpxa$. Known only to its finder, the vulnerability can be described
    by that singular state.
    
    As it becomes clear that the vulnerability affects multiple vendors'
    products, both finder/reporters and coordinators might begin to track
    the state of each individual vendor as a separate instance of the model.
    For example, if 3 vendors are known to be affected, but only 1 has been
    notified, the case might be considered to be in a
    [superposition](https://en.wikipedia.org/wiki/Superposition_principle) of
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

The above example implies a need to expand our notation.

!!! note "MPCVD Cases have Participant-Specific States"

    In the MPCVD case, we need to think of each state $q \in \mathcal{Q}$ as a set of states
    $q_M$:
    
    $$
    q_M \stackrel{\mathsf{def}}{=}\{ q_1,q_2,\dots,q_n \}
    $$
    
    where $q_i$ represents the state $q$ for the $i$th affected vendor
    and/or product. For example, $\{ {Vfdpxa}_1, {vfdpxa}_2 \}$ would
    represent the state in which vendor 1 has been notified but vendor 2 has
    not. 
    We have more to say about this in [Model Interactions](../process_models/model_interactions/index.md),
    but we'll borrow the diagram from there to illustrate the concept here.
  
    {% include-markdown "../process_models/model_interactions/_cs_global_local.md" %}

State transitions across vendors need not be simultaneous. Very often,
vendor notification occurs as new products and vendors are identified as
affected in the course of analyzing a vulnerability report. So the
individual events $\mathbf{V}_i$ in $\mathbf{V}_M$ (representing the
status of all the vendor notifications) might be spread out over a
period of time.

Some transitions are more readily synchronized than others. For example,
if an MPCVD case is already underway, and information about the vulnerability appears in
a public media report, we can say that $\mathbf{P}_M$ occurred
simultaneously for all coordinating vendors.

Regardless, in the maximal case, each vendor-product pair is effectively
behaving independently of all the others. Therefore:

!!! note "Dimensionality of an MPCVD Case"

    The maximum dimensionality of the MPCVD model for a case is
    
    $$
    D_{max} = 5 * N_{vprod}
    $$

    where $N_{vprod}$ represents the number of vendor-product pairs.

This is of course undesirable, as it would result in a wide distribution
of realized histories that more closely resemble the randomness
assumptions outlined above than a skillful, coordinated effort. Further
discussion of measuring MPCVD skill can be found below.

!!! tip "Reducing Dimensionality of MPCVD Cases is a good thing"

    For now, we posit that the goal of a good MPCVD
    process is to reduce the dimensionality of a given MPCVD case as
    much as is possible (i.e., to the 5 dimensions of a single vendor
    CVD case we have presented above).
    Experience shows that a full dimension reduction is
    unlikely in most cases, but that does not detract from the value of
    having the goal.

!!! tip "Reducing Complexity within a Vendor Organization"

    Vendors may be able to reduce their internal tracking
    dimensionality---which may be driven by things like component reuse
    across products or product lines---through in-house coordination of fix
    development processes. Within an individual vendor organization,
    PSIRTs are a common organizational structure to address this internal coordination process.

    - The [FIRST PSIRT Services Framework](https://www.first.org/standards/frameworks/psirts/psirt_services_framework_v1.1) provides guidance regarding vendors' internal
    processes for coordinating vulnerability response.
    - Additional guidance can be found in [ISO/IEC 30111:2019](https://www.iso.org/standard/69725.html).

Regardless, the cross-vendor dimension is largely the result of
component reuse across vendors, for example through the inclusion of
third party libraries or OEM SDKs. Visibility of cross-vendor component reuse
remains an unsolved problem, although efforts such as the [Software Bill of Materials](https://www.cisa.gov/sbom)
are promising in this regard. Thus, dimensionality reduction can
be achieved through both improved transparency of the software supply
chain and the process of coordination toward synchronized state
transitions, especially for $\mathbf{P}$, if not for $\mathbf{F}$ and
$\mathbf{D}$ as well.

As a result of the dimensionality problem, coordinators and other
parties to an MPCVD case need to decide how to apply
[disclosure policy rules](../process_models/em/principles.md) in cases where different products or vendors
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
state for all.

Another function could be to weight vendors and products by some
other factor, such as size of the installed user base, or even based on
a risk analysis of societal costs associated with potential actions.
Here we acknowledge that our example is under-specified: does the fifth
vendor (the one in $Vfdpxa$) represent a sizable fraction of the total
user base? Or does it concentrate the highest risk use cases for the
software? Challenges in efficiently assessing consistent answers to
these questions are easy to imagine. The status quo for
MPCVD appears consistent with defaulting to simple majority in the absence of
additional information, with consideration given to the distribution of
both users and risk on a case-by-case basis. At present, there is no
clear consensus on such policies, although we hope that future work can
use the model presented here to formalize the necessary analysis.

!!! tip "Integrating FIRST MPCVD Guidance"

    FIRST has published [Guidelines and Practices for Multi-Party Vulnerability Coordination and Disclosure](https://www.first.org/global/sigs/vulnerability-coordination/multiparty/guidelines-v1.1).
    Their guidance describes four use cases,
    along some with variations. Each use case variant includes a list of
    potential causes along with recommendations for prevention and responses
    when the scenario is encountered. A mapping of which use cases and
    variants apply to which subsets of states is given in the table below.
    
    | States                                                                                | FIRST Use Case   | Description |
    |---------------------------------------------------------------------------------------|------------------|-------------|
    | n/a                                                                                   | 0                | No vulnerability exists |
    | ${VFDp\cdot\cdot}$                                                                    | 1                | Vulnerability with no affected users |
    | ${V\cdot\cdot p\cdot\cdot}$                                                           | 1 Variant 1      | Product is deployed before vulnerability is discovered or fixed |
    | ${\cdot f\cdot\cdot\cdot\cdot}$                                                       | 2                | Vulnerability with coordinated disclosure |
    | ${\cdot fdP\cdot\cdot}$                                                               | 2 Variant 1      | Finder makes the vulnerability details public prior to remediation |
    | ${VFdP\cdot\cdot}$                                                                    | 2 Variant 2      | Users do not deploy remediation immediately |
    | (multiparty sync)                                                                     | 2 Variant 3      | Missing communication between upstream and downstream vendors |
    | ${VfdP\cdot\cdot}$                                                                    | 2 Variant 4      | Vendor makes the vulnerability details public prior to remediation |
    | ${Vfd\cdot\cdot\cdot}$                                                                | 2 Variant 5      | Vendor does not remediate a reported vulnerability |
    | (multiparty sync)                                                                     | 2 Variant 6      | Missing communication between peer vendors impedes coordination |
    | ${\cdot fdP\cdot\cdot}$                                                               | 2 Variant 7      | Coordinator makes vulnerability details public prior to remediation |
    | ${Vfdp\cdot\cdot}$, ${vfdp\cdot\cdot}$                                                | 2 Variant 8      | Finder reports a vulnerability to one vendor that may affect others using the same component |
    | ${\cdot fdP\cdot\cdot}$                                                               | 3                | Public disclosure of limited vulnerability information prior to remediation |
    | ${v\cdot\cdot P\cdot\cdot}$, ${v\cdot\cdot\cdot X\cdot}$, ${v\cdot\cdot\cdot\cdot A}$ | 4                | Public disclosure or exploitation of vulnerability prior to vendor awareness |
    | ${vf\cdot PX\cdot}$, ${vf\cdot P\cdot A}$                                             | 4 Variant 1      | Finder publishes vulnerability details and vulnerability is exploited |
    | ${v\cdot\cdot p\cdot A}$                                                              | 4 Variant 2      | Previously undisclosed vulnerability used in attacks |

## MPCVD Benchmarks

A common problem in MPCVD is that of fairness: coordinators are
often motivated to optimize the CVD process to maximize the deployment of
fixes to as many end users as possible while minimizing the exposure of
users of other affected products to unnecessary risks.

!!! tip "Benchmarking MPCVD"

    The model presented in this section provides a way for coordinators to
    assess the effectiveness of their MPCVD cases. In an
    MPCVD case, each
    vendor/product pair effectively has its own 6-event history $h_a$. 
    We can therefore recast MPCVD as a set of histories $\mathcal{M}$ drawn
    from the possible histories $\mathcal{H}$:

    $$
    \mathcal{M} = \{ h_1,h_2,...,h_m \textrm{ where each } h_a \in H \}
    $$

    Where $m = |\mathcal{M}| \geq 1$. The edge case when $|\mathcal{M}| = 1$
    is simply the regular (non-multiparty) case.

    We can then set desired criteria for the set $\mathcal{M}$, as in the
    benchmarks described in [Benchmarking](./benchmarking.md). In the MPCVD case, we propose to generalize the
    benchmark concept such that the median $\alpha_d$ should be
    greater than some benchmark constant $c_d$:
    
    $$
    Median({\alpha_d}) \geq c_d \geq 0
    $$
    
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

    $$
    Median(\{ \alpha_d(h) : h \in \mathcal{M} \}) \geq c_d > 0
    $$

    - The variance of each $\alpha_d$ for all histories
    $h \in \mathcal{M}$ should be low. The constant $\varepsilon$ is
    presumed to be small.

    $$
    \sigma^2(\{ \alpha_d(h) : h \in \mathcal{M} \}) \leq \varepsilon
    $$
