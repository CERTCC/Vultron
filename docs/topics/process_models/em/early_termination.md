# Early Termination and Other Special Cases

{% include-markdown "../../../includes/normative.md" %}

Here we describe a number of special cases that may arise during the
CVD process. These include 

- early termination of embargoes
- merging of multiple cases into a single case
- splitting a single case into multiple cases

## Early Termination

Embargoes sometimes terminate prior to the agreed date and time. This is
an unavoidable, if inconvenient, fact arising from three main causes:

1.  Vulnerability discovery capability is widely distributed across the
    world, and not all Finders become cooperative Reporters.

2.  Even among otherwise cooperative CVD Participants, leaks sometimes happen.

3.  Adversaries are unconstrained by CVD in their vulnerability discovery,
    exploit code development, and use of exploit code in attacks.

While many leaks are unintentional and due to miscommunication or errors
in a Participant's CVD process, the effect is the same
regardless of the cause. As a result,

!!! note ""

    Participants SHOULD be prepared with contingency plans in the event
    of early embargo termination.

Some reasons to terminate an embargo before the agreed date include the
following:


!!! note ""
  
    Embargoes SHALL terminate immediately when information about the
    vulnerability becomes public. Public information may include reports
    of the vulnerability or exploit code.
    ($q^{cs} \in \{ \cdot\cdot\cdot P \cdot\cdot, \cdot\cdot\cdot\cdot X \cdot \}$)

!!! note ""

    Embargoes SHOULD terminate early when there is evidence that the
    vulnerability is being actively exploited by adversaries.
    ($q^{cs} \in \{ \cdot\cdot\cdot\cdot\cdot A \}$)

!!! note ""

    Embargoes SHOULD terminate early when there is evidence that
    adversaries possess exploit code for the vulnerability.

!!! note ""

    Embargoes MAY terminate early when there is evidence that
    adversaries are aware of the technical details of the vulnerability.

The above is not a complete list of acceptable reasons to terminate an
embargo early. Note that the distinction between the *SHALL* in the
first item and the *SHOULD* in the second is derived from the reasoning
given in the [CS model](../cs/cs_model.md#cs-transitions)
, where we describe the CS model's transition function.
Embargo termination is the set of transitions described in the [EM model](index.md#terminate-embargo).

### Waiting for All Vendors to Reach _Fix Ready_ May Be Impractical.

It is not necessary for all Vendor Participants to reach
$q^{cs} \in VF\cdot\cdot\cdot\cdot$ before publication or embargo termination.
Especially in larger MPCVD cases, there comes a point where the net
benefit of waiting for every Vendor to be ready is outweighed by the
benefit of delivering a fix to the population that can deploy it. No
solid formula for this exists, but factors to consider include

- the market share of the Vendors in $q^{cs} \in VF \cdot\cdot\cdot\cdot$ compared to
those with $q^{cs} \in \cdot f\cdot\cdot\cdot\cdot$
- the software supply chain for fix delivery to Deployers
- the potential impact to critical infrastructure, public safety/health, or national security

!!! note ""

    Embargoes MAY terminate early when a quorum of Vendor Participants
    is prepared to release fixes for the vulnerability
    ($q^{cs}  \in VF\cdot\cdot\cdot\cdot$), even if some Vendors remain
    unprepared ($q^{cs} \in \cdot f \cdot\cdot\cdot\cdot$).

!!! note ""

    Participants SHOULD consider the software supply chain for the
    vulnerability in question when determining an appropriate quorum for
    release.

## Impact of Case Mergers on Embargoes

While relatively rare, it is sometimes necessary for two independent
CVD cases to be
merged into a single case. This can happen, for example, when two
Finders independently discover vulnerabilities in separate products and
report them to their respective (distinct) Vendors. On further
investigation, it might be determined that both reported problems stem
from a vulnerability in a library shared by both products. In this
scenario, each Reporter-Vendor pair might have already negotiated an
embargo for the case. Once the cases merge, the best option is usually
to renegotiate a new embargo for the new case.

!!! note ""

    A new embargo SHOULD be proposed when any two or more
    CVD cases are to be merged into a single case and multiple parties have agreed to
    different embargo terms prior to the case merger.

!!! note ""

    If no new embargo has been proposed, or if agreement has not been
    reached, the earliest of the previously accepted embargo dates SHALL
    be adopted for the merged case.

!!! note ""

    Participants MAY propose revisions to the embargo on a merged case
    as usual.

## Impact of Case Splits on Embargoes

It is also possible that a single case needs to be split into multiple
cases after an embargo has been agreed to. For example, consider a
vulnerability that affects two widely disparate fix supply chains, such
as a library used in both SAAS and OT environments. The
SAAS Vendors might
be well positioned for a quick fix deployment while the
OT Vendors might
need considerably longer to work through the logistics of delivering
deployable fixes to their customers. In such a case, the case
Participants might choose to split the case into its respective supply
chain cohorts to better coordinate within each group.

!!! note ""

    When a case is split into two or more parts, any existing embargo
    SHOULD transfer to the new cases.

!!! note ""

    If any of the new cases need to renegotiate the embargo inherited
    from the parent case, any new embargo SHOULD be later than the
    inherited embargo.

!!! note ""

    In the event that an earlier embargo date is needed for a child
    case, consideration SHALL be given to the impact that ending the
    embargo on that case will have on the other child cases retaining a
    later embargo date. In particular, Participants in each child case
    should assess whether earlier publication of one child case might
    reveal the existence of or details about other child cases.

!!! note ""

    Participants in a child case SHALL communicate any subsequently
    agreed changes from the inherited embargo to the Participants of the
    other child cases.

Note that it may not always be possible for the split cases to have
different embargo dates without the earlier case revealing the existence
of a vulnerability in the products allocated to the later case. For this
reason, it is often preferable to avoid case splits entirely.

