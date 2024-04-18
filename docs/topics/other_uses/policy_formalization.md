# Disclosure Policy Formalization

{% include-markdown "../../includes/not_normative.md" %}

In this section, we apply our model to the formalization of
vulnerability disclosure policies. This discussion is not intended to be
a complete formalization of all possible policy choices; rather, we seek
to relate how some aspects of disclosure policies might be formalized
using our model. In particular, we will look at applications of the
model to embargoes and service level expectations.

<!-- for spacing -->
<br/>

!!! vultron "Embargo Policy Formalization"

    An embargo is an agreement between coordinating stakeholders to keep
    information about a vulnerability private until some exit condition
    has been met. Embargoes are a common feature of CVD, and the model
    gives us a way of formally specifying the conditions under which
    initiating or maintaining an embargo may or may not be appropriate.
    The [Embargo Management (EM) model](../process_models/em/index.md)
    is a core part of the Vultron Protocol, so we will not repeat that
    discussion here. Likewise, we'll also just point readers to the
    [Model Interactions](../process_models/model_interactions/index.md) 
    section for a discussion of how the EM model interacts with policies and the 
    other models in the Vultron Protocol.

## CVD Service Level Expectations

Closely related to CVD embargoes are CVD SLEs. Disclosure policies specify commitments by
coordinating parties to ensure the occurrence of certain state
transitions within a specific period of time. While the model presented
here does not directly address timing choices, we can point out some
ways to relate the model to those choices. Specifically, we intend to
demonstrate how disclosure policy SLEs can be stated as rules triggered within
subsets of states or by particular transitions between subsets of states
in $\mathcal{Q}$.

!!! example "SLEs and Publication Timing"

    For example, a finder, reporter, or coordinator might commit to
    publishing information about a vulnerability 30 days after vendor
    notification. This translates to starting a timer at
    ${v} \xrightarrow{\mathbf{V}} {V}$ and ensuring
    ${Vp} \xrightarrow{\mathbf{P}} {VP}$ when the timer expires. Notice that
    the prospect of ${Vfp} \xrightarrow{\mathbf{P}} {VfP}$ is often used to
    motivate vendors to ensure a reasonable SLE to produce fixes
    (${Vf} \xrightarrow{\mathbf{F}} {VF}$) 
    (See for example [Optimal Policy for Software Vulnerability Disclosure](https://www.jstor.org/stable/20122417) by Arora, Telang, and Xu).

!!! example "SLEs and Fix Readiness Timing"

    Similarly, a vendor might commit to providing public fixes within 5
    business days of report receipt. In that case, the
    SLE timer would
    start at ${vfp} \xrightarrow{\mathbf{V}} {Vfp}$ and and end at one of
    two transitions: First, the "normal" situation in which the vendor
    creates a fix and makes it public along with the vulnerability
    ($\mathbf{F} \prec \mathbf{P}$, i.e.,
    ${VFp} \xrightarrow{\mathbf{P}} {VFP}$). Second, a ["zero day"](./zero_day.md)
    situation in which events outside the vendor's control cause the
    ${Vfp} \xrightarrow{\mathbf{P}} {VfP}$ transition to occur prior to the
    fix being ready (${VfP} \xrightarrow{\mathbf{F}} {VFP}$), i.e,
    $\mathbf{P} \prec \mathbf{F}$. Likewise, the
    ${Vfp} \xrightarrow{\mathbf{P}} {VfP} \xrightarrow{\mathbf{F}} {VFP}$
    path might also occur when a vendor has set their embargo timer too
    aggressively for their development process to keep up.

    It is therefore in the vendor's interest to tune their
    SLE to reduce the likelihood for unexpected public awareness ($\mathbf{P}$) while
    providing sufficient time for $\mathbf{F}$ to occur, optimizing to
    achieve $\mathbf{F} \prec \mathbf{P}$ in a substantial fraction of
    cases. As future work, measurement of both the incidence and timing of
    embargo failures through observation of $\mathbf{P}$, $\mathbf{X}$, and
    $\mathbf{A}$ originating from $\mathcal{Q}_{E}$ could give insight into
    appropriate vendor SLEs for fix readiness ($\mathbf{F}$).

!!! example "SLEs and Fix Deployment Timing"

    Service providers and VM practitioners might similarly describe
    their SLEs in terms
    of timing between states. Such policies will likely take the form of
    commitments to limit the time spent in ${FdP}$. When the vendor has
    already produced a patch, the clock starts at
    ${Fdp} \xrightarrow{\mathbf{P}} {FdP}$, whereas if the vulnerability
    becomes public prior to patch the clock starts at
    ${fdP} \xrightarrow{\mathbf{F}} {FdP}$. In both cases, the timer ends at
    ${FdP} \xrightarrow{\mathbf{D}} {FDP}$.

!!! tip "Formalizing Policy Statements"

    Future formal definitions of policy statements might take the general
    form of specifications including

    - Starting state ($q \in \mathcal{Q}$) or subset of states
    ($S \subset \mathcal{Q}$)

    - Expected transitions ($\sigma \in \Sigma$) and
    SLEs around their
    timing, including possible constraints such as "not before" and "no
    later than" specifications

    - An indication of constraint rigidity (negotiable, fixed, [*MUST*,
    *SHOULD*, *MAY*](https://datatracker.ietf.org/doc/html/rfc2119), etc.)

    - Potential exceptions in the form of other transitions
    ($\sigma \in \Sigma$) that might alter expected behavior, and a
    description of the anticipated response.

!!! info "Policy Formalization and Embargo Conflict Resolution"

    We cover this more extensively in our discussion of the [EM](../process_models/em/index.md) model,
    but one reason to formalize policy definitions is the potential to
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
