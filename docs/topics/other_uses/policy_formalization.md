# Disclosure Policy Formalization {#sec:policy_formalism}

In this section, we apply our model to the formalization of
vulnerability disclosure policies. This discussion is not intended to be
a complete formalization of all possible policy choices; rather, we seek
to relate how some aspects of disclosure policies might be formalized
using our model. In particular, we will look at applications of the
model to embargoes and service level expectations.

## Embargo Initiation Policies

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
§[6.2](#sec:mpcvd){== TODO fix ref to sec:mpcvd ==}. Here we
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

## Embargo Continuation Policies

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
[\[eq:embargo_start\]](#eq:embargo_start){== TODO fix ref to eq:embargo_start ==}, and remain viable through any state in
$\mathcal{Q}_{E}$ as in Eq.
[\[eq:embargo_viable\]](#eq:embargo_viable){== TODO fix ref to eq:embargo_viable ==}. This in turn gives us specific things to
look for in order to determine when to end an embargo:

- The embargo timer has expired.

- Any observation of $\mathbf{P}$, $\mathbf{X}$, or $\mathbf{A}$ has
    been made ($q \not\in {pxa}$).

- $\mathbf{F}$ or $\mathbf{D}$ have occurred
    ($q \in \{{VFdpxa}, {VFDpxa}\})$, and no reasons specific to the
    case to maintain the embargo remain.

- Any other embargo exit rules---such as those specified in the
    relevant disclosure policies---have been triggered.

## CVD Service Level Expectations

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

- Starting state ($q \in \mathcal{Q}$) or subset of states
    ($S \subset \mathcal{Q}$)

- Expected transitions ($\sigma \in \Sigma$) and
    SLEs around their
    timing, including possible constraints such as "not before" and "no
    later than" specifications

- An indication of constraint rigidity (negotiable, fixed, *MUST*,
    *SHOULD*, *MAY* [@bradner1997rfc2119], etc.)

- Potential exceptions in the form of other transitions
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
