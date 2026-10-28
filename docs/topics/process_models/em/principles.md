---
stakeholder_type: [cvd-practitioner]
level: 200
page_type: explanation
subject: protocol
description: >
  What an embargo is for, and the norms Participants follow while one is in force.
---

# Embargo Principles

{% include-markdown "../../../includes/specification_governs.md" %}

An embargo is a way to delay public disclosure of a vulnerability while defenses are prepared.
For example, an embargo can last until fix development is complete for a reasonable quorum of Vendors.

The goal of the EM process is not an exact publication schedule that every Participant follows.
Rather,

!!! tip "Embargo Management Process Goal"

    The goal of the Embargo Management process is to establish a window from the present to some future time.
    During this window, _Participants are expected to not publish or otherwise disclose_ information about the vulnerability to non-Participants outside of the CVD case.

So we define an embargo as follows:

{% include-markdown "./_embargo_defn.md"   %}

## Embargoes Are a Social Agreement

An embargo is a social agreement between independent parties.
These parties act so that users get vulnerability fixes in a timely manner, and so that attackers get as little advantage as possible in the interim.
But an embargo is not always appropriate or useful in a given CVD case.

With this in mind, we give the following principles as guidance.
We start with some norms of behavior.
These norms define what it means to cooperate with an embargo.

!!! note ""

    Embargo Participants SHOULD NOT knowingly release information about an embargoed case until either

    1.  all proposed embargoes have been explicitly rejected

    2.  no proposed embargo has been explicitly accepted in a timely manner

    3.  the expiration date/time of an accepted embargo has passed

    4.  an accepted embargo has been terminated prior to the embargo expiration date and time due to other reasons (e.g., those outlined in [Early Termination](early_termination.md))

!!! note ""
    Additional Participants MAY be added to an existing embargo upon accepting the terms of that embargo.

!!! note ""
    Adding Participants to an existing embargo SHALL NOT constitute "release" or "publication" so long as those Participants accept the terms of the embargo.

For more information, see [Adding Participants](working_with_others.md).

## Embargoes are Limited Short-Term Agreements

When all other facts about a vulnerability report are equal, two factors have a large effect on the success or failure of an embargo.
These factors are scale and duration.
The more people that are part of an embargo, the more likely the embargo is to fail.

!!! note ""
    Embargo participation SHOULD be limited to the smallest possible set of individuals and organizations needed to adequately address the vulnerability report.

Similarly, the longer an embargo lasts, the more likely it is to fail.

!!! note ""
    Embargo duration SHOULD be limited to the shortest duration possible to adequately address the vulnerability report.

We also need to set a few norms for embargo timing.

!!! note ""  
    An embargo SHALL specify an unambiguous date and time as its endpoint.

!!! note ""
    An embargo SHALL NOT be used to indefinitely delay publication of vulnerability information, whether through repeated extension or by setting a long-range endpoint.

!!! note ""
    An embargo SHALL begin at the moment it is accepted.

!!! note ""
    Embargoes SHOULD be of short duration, from a few days to a few months.

{% include-markdown "./_nda_sidebar.md" %}

## Embargo Participants Are Free to Engage or Disengage

As we [just described](#cvd-embargoes-are-not-ndas), an embargo is not the same thing as an NDA, even if the two have similar effects.
An NDA is a contract, so a party that breaks it can get civil or even criminal penalties.
CVD embargoes have no such legal framework.
So CVD Participants are free to enter or exit an embargo at any time, for any reason.
In fact, CVD Participants do not have to agree to any embargo at all.

But whatever they choose, Participants should be clear with other Participants about their status and intentions.
There are a few good reasons to exit an embargo early.
For more information, see [Early Termination](early_termination.md).

!!! note ""
    Participants MAY propose a new embargo or revision to an existing embargo at any time within the constraints outlined in [Negotiating Embargoes](negotiating.md).

!!! note ""
    Participants MAY reject proposed embargo terms for any reason.

!!! note ""
    Participants in an embargo MAY exit the embargo at any time.

### Leaving an Embargo is Not Embargo Termination

When a Participant leaves an embargo, this is not necessarily the same as the termination of the embargo itself.
Embargo termination corresponds to the $q^{em} \in \{A,R\} \xrightarrow{t} X$ transition in the [EM formal model](formal_model.md#terminate-embargo).
It shows a consensus among the case Participants that the embargo no longer applies.
When a Participant leaves an *Active* embargo, the embargo agreement between the other Participants stays intact.
But the Participant that leaves is no longer involved in the case.

!!! note ""
    Participants stopping work on a case SHOULD notify remaining Participants of their intent to adhere to or disregard any existing embargo associated with the case.

!!! note ""
    Participants SHOULD continue to comply with any active embargoes to which they have been a part, even if they stop work on the case.

!!! note ""
    Participants who leave an *Active* embargo SHOULD be removed by the remaining Participants from further communication about the case.

!!! tip inline end "Embargo Engagement and Adherence"

    We return to these concepts with the `case_engagement` attribute and the per-embargo consent rows described in [Case Model](../../case_lifecycle/case_model.md).
    For the per-(participant, embargo) consent state machine, see [Embargo Lifecycle](../../behavior_logic/use-cases/embargo-lifecycle.md).

These points mean that Participants need to track the status of other Participants.
This status includes their adherence to the embargo and their engagement with the case.

### Leaving an Embargo May Have Consequences

As we note in the [CVD Guide](https://certcc.github.io/CERT-Guide-to-CVD/howto/coordination/response_pacing){:target="_blank"}, CVD is an iterated game, and actions have consequences.
If a Participant leaves an embargo early in one case, this can affect how willing Participants are to cooperate in later cases.

!!! note ""
    A Participant's refusal to accept embargo terms MAY result in that Participant being left out of the CVD case entirely.

!!! note ""
    Participants SHOULD consider other Participants' history of cooperation when evaluating the terms of a proposed embargo.

## Embargo Termination is Not the Same as Publication

Finally, embargo termination *removes a constraint*.
It does not *add an obligation*.

!!! note ""
    Participants SHOULD NOT publish information about the vulnerability when there is an active embargo.

!!! note ""
    Participants MAY publish information about the vulnerability when there is no active embargo.

!!! note ""
    Embargo termination SHALL NOT be construed as an obligation to publish.

[Adding Participants](working_with_others.md) discusses how to decide whom to invite to a CVD case.

## Doing It on the Wire

- [How to Establish an Embargo](../../../howto/activitypub/activities/establish_embargo.md) — propose, accept and activate an embargo.
- [How to Revise or Terminate an Embargo](../../../howto/activitypub/activities/manage_embargo.md) — change or end an active embargo.

{% include-markdown "../../../start/_paths/coordinate-cases/topics__process_models__em__principles.md" %}
