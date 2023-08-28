# Early Termination 

{% include-markdown "../../../includes/normative.md" %}

Embargoes sometimes terminate prior to the agreed date and time. This is
an unavoidable, if inconvenient, fact arising from three main causes:

1.  Vulnerability discovery capability is widely distributed across the
    world, and not all Finders become cooperative Reporters.

2.  Even among otherwise cooperative CVD Participants, leaks sometimes happen.

3.  Adversaries are unconstrained by CVD in their vulnerability discovery,
    exploit code development, and use of exploit code in attacks.

## Be Prepared for Embargo Termination

While many leaks are unintentional and due to miscommunication or errors in a Participant's CVD process, the effect is
the same regardless of the cause. As a result,

!!! note ""

    Participants SHOULD be prepared with contingency plans in the event
    of early embargo termination.

## Reasons to Terminate an Embargo Early

Some reasons to terminate an embargo before the agreed date include the
following:


!!! note ""
  
    ???+ note inline end "Formalism"

        $q^{cs} \in \{ \cdot\cdot\cdot P \cdot\cdot, \cdot\cdot\cdot\cdot X \cdot \}$

    Embargoes SHALL terminate immediately when information about the
    vulnerability becomes public. Public information may include reports
    of the vulnerability or exploit code.
    

!!! note ""

    ???+ note inline end "Formalism"

        $q^{cs} \in \{ \cdot\cdot\cdot\cdot\cdot A \}$

    Embargoes SHOULD terminate early when there is evidence that the
    vulnerability is being actively exploited by adversaries.

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

## Waiting for All Vendors to Reach _Fix Ready_ May Be Impractical.

???+ note inline end "Fix Ready Definition"

    $$q^{cs} \in VF\cdot\cdot\cdot\cdot$$

It is not necessary for all Vendor Participants to reach _Fix Ready_ before publication or embargo termination.
Especially in larger MPCVD cases, there comes a point where the net
benefit of waiting for every Vendor to be ready is outweighed by the
benefit of delivering a fix to the population that can deploy it. No
solid formula for this exists, but factors to consider include

- the market share of the Vendors in _Fix Ready_ ($q^{cs} \in VF \cdot \cdot \cdot \cdot$) compared to
those that are not ($q^{cs} \in \cdot f \cdot \cdot \cdot \cdot$)
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

