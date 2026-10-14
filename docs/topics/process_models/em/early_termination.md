---
stakeholder_type: [cvd-practitioner]
level: 300
description: >
  The events that end an embargo before its agreed time, how a termination
  records why it ended, and what happens when the end time passes.
---

# Early Termination

{% include-markdown "../../../includes/normative.md" %}

Embargoes sometimes terminate prior to the agreed date and time. This is
an unavoidable, if inconvenient, fact arising from three main causes:

1. Vulnerability discovery capability is widely distributed across the
    world, and not all Finders become cooperative Reporters.

2. Even among otherwise cooperative CVD Participants, leaks sometimes happen.

3. Adversaries are unconstrained by CVD in their vulnerability discovery,
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
given in the [CS model](../cs/cs_model.md)
, where we describe the CS model's transition function.
Embargo termination is the set of transitions described in the [EM formal model](formal_model.md#terminate-embargo).
When an embargo terminates, every Participant's [embargo consent](../../behavior_logic/use-cases/embargo-lifecycle.md#which-messages-move-consent) moves to the terminal *Unbound (exited)*, because there is no longer an embargo to agree to, and a terminated embargo cannot be re-joined ([§7.3 Relationship to Embargo Consent in the Vultron Protocol Specification](../../../reference/vultron-spec/tracking-models.md#73-relationship-to-embargo-consent)).
A Participant who wants to be bound by a later embargo must agree to it afresh.

## Recording Why an Embargo Ended

Every termination records what ended the embargo: it reached its end time (`END_TIME_REACHED`), or it ended early (`EARLY`).
The termination message carries that reason, and every Participant records it.
The Case Manager also records why the embargo ended when it knows.
An embargo ended by public awareness, a public exploit or observed attacks is recorded as `EARLY`, caused by that threat signal.
Other causes of an early end, such as the ones above, are not yet named, and the set of causes is left open to grow.
The cause stays with the Case Manager's record and is not sent in the termination message.

## When the End Time Passes

An embargo does not end by itself when its end time passes.
The Case Manager ends it with the reason `END_TIME_REACHED`, and the termination runs the same steps as any other: open proposals are canceled, the case leaves the embargo, and every Participant is told.
The Case Manager checks the end time the next time it handles the case, so no scheduler is needed.
An outside service, such as a [Sentinel](../../../reference/glossary.md) watching embargo timers, can also ask the Case Manager to end the embargo at its end time.
The two requests share one path: whichever arrives second finds the embargo already ended, and nothing more is sent.
A termination that claims the end time was reached before it was is refused.

## Waiting for All Vendors to Reach *Fix Ready* May Be Impractical

???+ note inline end "Fix Ready Definition"

    $$q^{cs} \in VF\cdot\cdot\cdot\cdot$$

It is not necessary for all Vendor Participants to reach *Fix Ready* before publication or embargo termination.
Especially in larger MPCVD cases, there comes a point where the net
benefit of waiting for every Vendor to be ready is outweighed by the
benefit of delivering a fix to the population that can deploy it. No
solid formula for this exists, but factors to consider include

- the market share of the Vendors in *Fix Ready* ($q^{cs} \in VF \cdot \cdot \cdot \cdot$) compared to
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

## Doing It on the Wire

- [How to Revise or Terminate an Embargo](../../../howto/activitypub/activities/manage_embargo.md) — end an active embargo, early or at its agreed time.
- [How to Establish an Embargo](../../../howto/activitypub/activities/establish_embargo.md) — put a case back under embargo, where the case is still embargo-eligible.
