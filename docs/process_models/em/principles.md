# Embargo Principles

Embargoes are a means of inhibiting public disclosure of a vulnerability
while defenses are prepared (e.g., until fix development has completed
for a reasonable quorum of Vendors). The goal of the
EM process is not to
establish an exact publication schedule for every Participant to adhere
to. Rather, it is to establish a window spanning from the present to
some future time, during which Participants are expected not to publish
or otherwise disclose information about the vulnerability to
non-Participants outside of the CVD case.

## Embargoes Are a Social Agreement

An embargo is a social agreement between independent parties acting in
the interest of providing vulnerability fixes to users in a timely
manner while minimizing attacker advantage in the interim. However,
embargoes are not always appropriate or useful within the context of any
given CVD case.

With that in mind, we offer the following principles as guidance. We
begin with some behavioral norms that define what it means to cooperate
with an embargo.

!!! note ""

    Embargo Participants SHOULD NOT knowingly release information about
    an embargoed case until either

    1.  all proposed embargoes have been explicitly rejected

    2.  no proposed embargo has been explicitly accepted in a timely
        manner

    3.  the expiration date/time of an accepted embargo has passed

    4.  an accepted embargo has been terminated prior to the embargo
        expiration date and time due to other reasons (e.g., those
        outlined in
        {== §[1.2.7](#sec:early_termination){reference-type="ref"
        reference="sec:early_termination"} ==})

!!! note ""
    Additional Participants MAY be added to an existing embargo upon
    accepting the terms of that embargo.

!!! note ""
    Adding Participants to an existing embargo SHALL NOT constitute
    "release" or "publication" so long as those Participants accept the
    terms of the embargo.

See
    {== §[1.2.10](#sec:inviting_others){reference-type="ref"
    reference="sec:inviting_others"} ==}.

## Embargoes are Limited Short-Term Agreements


Given all other facts about a vulnerability report being equal, there
are two factors that contribute significantly to the success or failure
of an embargo: scale and duration. The more people involved in an
embargo, the more likely the embargo is to fail.

!!! note ""
    Embargo participation SHOULD be limited to the smallest possible set
    of individuals and organizations needed to adequately address the
    vulnerability report.

Similarly, the longer an embargo lasts, the more likely it is to fail.

!!! note ""
    Embargo duration SHOULD be limited to the shortest duration possible
    to adequately address the vulnerability report.

Furthermore, we need to establish a few norms related to embargo timing.

!!! note ""  
    An embargo SHALL specify an unambiguous date and time as its
    endpoint.

!!! note ""
    An embargo SHALL NOT be used to indefinitely delay publication of
    vulnerability information, whether through repeated extension or by
    setting a long-range endpoint.

!!! note ""
    An embargo SHALL begin at the moment it is accepted.

!!! note ""
    Embargoes SHOULD be of short duration, from a few days to a few
    months.

{% include-markdown "nda-sidebar.md" %}

## Embargo Participants Are Free to Engage or Disengage {#sec:embargo_engagement}

As we [just described](#cvd-embargoes-are-not-ndas), an embargo is not the
same thing as an NDA, even if they have similar effects.
Because it is a contract, an NDA can carry civil or even criminal
penalties for breaking it. CVD embargoes have no such legal framework.
Hence, CVD
Participants are free to enter or exit an embargo at any time, for any
reason. In fact, CVD Participants are not obliged to agree to
any embargo at all. However, regardless of their choices, Participants
should be clear about their status and intentions with other
Participants. There are a few good reasons to exit an embargo early.
(See {== §[1.2.7](#sec:early_termination){reference-type="ref"
reference="sec:early_termination"} ==}.)
 
!!! note ""
    Participants MAY propose a new embargo or revision to an existing
    embargo at any time within the constraints outlined in
    {== §[1.2.4](#sec:entering_an_embargo){reference-type="ref"
    reference="sec:entering_an_embargo"} ==}.

!!! note ""
    Participants MAY reject proposed embargo terms for any reason.

!!! note ""
    Participants in an embargo MAY exit the embargo at any time.

### Leaving an Embargo is Not Embargo Termination

Note that a Participant leaving an embargo is not necessarily the same
as the embargo itself terminating. 
Embargo termination corresponds to the $q^{em} \in \{A,R\} \xrightarrow{t} X$ transition in the
[EM model](index.md) and reflects a consensus among case Participants that the embargo no longer
applies. A Participant leaving an *Active* embargo means that the
embargo agreement between other Participants remains intact, but that
the leaving Participant is no longer involved in the case.

!!! note ""
    Participants stopping work on a case SHOULD notify remaining
    Participants of their intent to adhere to or disregard any existing
    embargo associated with the case.

!!! note ""
    Participants SHOULD continue to comply with any active embargoes to
    which they have been a part, even if they stop work on the case.

!!! note ""
    Participants who leave an *Active* embargo SHOULD be removed by the
    remaining Participants from further communication about the case.

These points imply a need for Participants to track the status of other
Participants with respect to their adherence to the embargo and
engagement with the case. We will return to these concepts with the
{== $case\_engagement_ and _embargo\_adherence$ attributes described in
 §[\[sec:case_object_participant_class\]](#sec:case_object_participant_class){reference-type="ref"
reference="sec:case_object_participant_class"} ==}.

### Leaving an Embargo May Have Consequences

CVD is an iterated game, and actions have consequences. Leaving an embargo early in one
case may have repercussions to Participants' willingness to cooperate in
later cases.

!!! note ""
    A Participant's refusal to accept embargo terms MAY result in that
    Participant being left out of the CVD case entirely.

!!! note ""
    Participants SHOULD consider other Participants' history of
    cooperation when evaluating the terms of a proposed embargo.

## Embargo Termination is Not the Same as Publication

Finally, embargo termination removes a constraint rather than adding an
obligation.

!!! note ""
    Participants SHOULD not publish information about the vulnerability
    when there is an active embargo.

!!! note ""
    Participants MAY publish information about the vulnerability when
    there is no active embargo.

!!! note ""
    Embargo termination SHALL NOT be construed as an obligation to
    publish.

A discussion of how to decide who to invite to participate in a
CVD case is addressed in [Adding Participants](working_with_others.md).
