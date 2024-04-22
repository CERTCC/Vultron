# Adding Participants to an Embargoed Case

{% include-markdown "../../../includes/normative.md" %}

Here we describe the who and when of adding Participants to
an embargoed case.

As anyone who has tried to schedule a meeting with multiple attendees
can attest, multi-party scheduling can be difficult. When that schedule
must also accommodate work completion schedules for an
MPCVD case, it becomes even harder. In [Default Embargoes](#default-embargoes),
we laid out a heuristic for resolving multiple embargo proposals, *The Shortest Embargo Proposed
Wins*.
More specifically, we recommended that Participants *accept* the
earliest proposed end date and immediately propose and evaluate the rest
as potential revisions. This principle applies to any
MPCVD case, even at its outset.

## Start Early, Start Small

Embargo negotiations can become contentious in larger cases. Many
MPCVD cases grow over time, and it is usually easier to establish an embargo with a
smaller group than a larger one. Conflict resolution via consensus
agreement is fine if it works. In fact, in scenarios where Participants
who have already agreed to an embargo get to choose who else to add to
the embargo, the existing consensus can be a strong influence for the
new Participant to consent to the existing agreement.

In other words, it is usually preferable to present an already-accepted
embargo to new Participants and get their agreement before potentially
revising the embargo than it is to wait for a large multi-party
negotiation to succeed before establishing an embargo in the first
place.

!!! tip inline end "See also"

    [ISO/IEC 29147:2018](https://www.iso.org/standard/72311.html)

When consensus fails, however, it may be helpful for the group to
appoint a case lead to resolve any conflicts. Such scenarios are often
an opportunity for a third-party Coordinator to be engaged.

Therefore,

!!! note ""

    Participants SHOULD attempt to establish an embargo as early in the
    process of handling the case as possible.

!!! note ""

    Participants SHOULD follow consensus agreement to decide embargo
    terms.

!!! note ""

    When consensus fails to reach agreement on embargo terms,
    Participants MAY appoint a case lead to resolve conflicts.

!!! note ""

    Participants MAY engage a third-party Coordinator to act as a
    neutral third-party case lead to resolve conflicts between
    Participants during the course of handling a case.

## Who to Invite

The Finder/Reporter is, by definition, a Participant in any
CVD case by virtue
of their knowledge of the vulnerability in the first place. Additional
Participants usually fall into one of three categories:

!!! note ""

    All known Vendors of affected software SHOULD be included as
    Participants.

!!! note ""

    Third-party Coordinators MAY be included as Participants.

!!! note ""

    Other parties MAY be included as Participants when necessary and
    appropriate.

!!! example "Examples of Other Participants"

    Examples of other Participants we have observed in past cases include

    - Deployers
    - Subject matter experts
    - Government agencies with relevant regulatory oversight or critical infrastructure protection responsibilities.

## Adding Participants to an Existing Embargo

Adding new Participants to a case with an existing embargo might require
the new Participant to accept the embargo prior to receiving the report.

!!! note ""

    When inviting a new Participant to a case with an existing embargo,
    the inviting Participant SHALL propose the existing embargo to the
    invited Participant.

!!! note ""

    A newly invited Participant to a case with an existing embargo
    SHOULD accept the existing embargo.

!!! note ""

    The inviting Participant SHOULD NOT share the vulnerability report
    with the newly invited Participant unless the new Participant has
    accepted the existing embargo.

!!! note ""

    The inviting Participant MAY interpret the potential Participant's
    default embargo contained in their published vulnerability
    disclosure policy in accordance with the default acceptance
    strategies listed in [Default Embargoes](#default-embargoes).

!!! note ""

    A newly invited Participant to a case with an existing embargo MAY
    propose a revision after accepting the existing embargo.

## When to Invite Participants

In MPCVD there are practical considerations to be made regarding the timing of *when*
to notify individual Participants. The primary factor in these decisions
stems from the interaction of the *Active* embargo with the potential
Participant's existing (explicit or implicit) disclosure policy.

### Participants with Disclosure Policies Shorter Than an Existing Embargo

Adding a potential Participant with a known default disclosure policy
*shorter* than an extant embargo leaves Participants with these options
to choose from:

1. Shorten the existing embargo to match the potential Participant's
    policy.

2. Propose the existing embargo to the potential Participant, and, upon
    acceptance, share the report with them.

3. Delay notifying the potential Participant until their default policy
    aligns with the existing embargo.

4. Avoid including the potential Participant in the embargo entirely.

!!! example "Example: A Vendor with a short default embargo"

    Say a Vendor has a seven-day maximum public disclosure policy.
    Participants in a case with an existing embargo ending in three weeks might choose to notify that Vendor two weeks
    from now to ensure that even the default disclosure timeline remains compatible with the extant embargo.

!!! note ""

    Participants with short default embargo policies SHOULD consider
    accepting longer embargoes in MPCVD cases.

!!! note ""

    Participants in an MPCVD case MAY delay notifying potential
    Participants with short default embargo policies until their policy
    aligns with the agreed embargo.

### Participants with Disclosure Policies Longer Than an Existing Embargo

Similarly, adding a Participant with a known default disclosure policy
*longer* than an extant embargo leaves Participants with the following
options to choose from:

1. Lengthen the existing embargo to match the potential Participant's
    policy.

2. Propose the existing embargo to the potential Participant, and, upon
    acceptance, share the report with them.

3. Avoid including the potential Participant in the embargo entirely.

In the case of a Vendor with a *longer* default policy than the existing
embargo, it is still preferable to give them as much lead time as
possible *even* if it is not possible to extend the embargo to their
preferred timing.

!!! note ""

    In the interest of receiving the report in the first place,
    potential Participants with a longer default policy than an existing
    case SHOULD accept the embargo terms offered.

!!! note ""

    After accepting an existing embargo, newly invited Participants with
    a longer default policy than an existing case MAY propose a revision
    to the existing embargo, if desired, to accommodate their
    preferences.

!!! note ""

    Existing Participants MAY *accept* or *reject* such a proposed
    revision as they see fit.

!!! note ""

    Participants in a case with an existing embargo SHOULD notify
    Vendors with a longer default embargo policy.

!!! note ""

    Participants in a case with an existing embargo MAY choose to extend
    the embargo to accommodate a newly added Participant.

### Untrustworthy Participants

Unfortunately, not all potential CVD Participants are equally trustworthy with
vulnerability information.

!!! example "Examples of Untrustworthy Participants"

    We can provide a few examples of potentially untrustworthy Participants:
    
    - A Participant might have sub-par operational security or even business practices that result in adversaries often
    finding out about vulnerabilities in their products before the end of an embargo period.
    - Participants might be subject to regulatory regimes in which they are required by law to share known
    vulnerabilities with government agencies having oversight responsibilities. Depending on the jurisdiction, these
    agencies might not be bound by the same embargoes as the other Participants in the case.
    - The Participants in a case might consider a government agency to be an adversary itself and therefore not
    trustworthy with non-public vulnerability information.

    In these or similar scenarios, these concerns might lead to the exclusion of otherwise trustworthy Participants from an embargo.

!!! note ""

    Participants that are known to leak or provide vulnerability
    information to adversaries either as a matter of policy or
    historical fact SHOULD be treated similar to Participants with brief
    disclosure policies.

!!! tip "My Adversary Is *Not Necessarily* Your Adversary"

    Trustworthiness has a strong subjective component, and individual perspectives on who is or is not trustworthy
    can vary widely.
    Thus, while acknowledging that *adversary* is not a universally agreed-upon category, the definition of *adversary* in the above
    is left to individual Participants.

The maximal interpretation of the above is that untrustworthy
Participants are left to be notified by the publication of the
vulnerability report. This is the equivalent of treating them like a
Participant with a default zero-day maximum embargo policy.

### Coordinators

Third-party Coordinators, as Participants who are neither Finders nor
Vendors, often play an important role in MPCVD cases, especially those with broad impact
across the software supply chain or with acute critical infrastructure
or public safety impacts. Most Coordinators strive to be consistent in
their MPCVD
practices and have well-documented disclosure policies along with
significant histories of handling previous cases. All of these factors
make the argument for including third-party Coordinators in
CVD cases of
sufficient complexity, impact, or importance.

### Other Parties

Some Participants in CVD have their own policies that prohibit notification of any parties unable to directly contribute
to the development of a fix for a particular vulnerability.
Typically, these policies take the form of "only Vendors of affected products" or similar such restrictions.

The CERT/CC's position as a third-party Coordinator in numerous cases is that this approach can be appropriate for
straightforward scenarios, such as those in which a Vendor is in direct contact with their downstream Vendors and can
coordinate the response within that community.

However, it falls short in some cases, such as the following:

- Vulnerabilities are found to affect a broad spectrum of Vendors and
    products, especially when cases cross industry sectors or otherwise
    include Participants having widely divergent operational tempos or
    software delivery models.

- Vulnerabilities affect systems deployed in high-impact niches, such
    as critical infrastructure, public safety, and national security.

- Outside expertise is needed to understand the implications or impact
    of a vulnerability beyond the participating Vendors; sometimes the
    most knowledgeable parties work for someone else.

## Consequences of Non-Compliance

Considering multiple cases over time, MPCVD can be thought of as an [iterated game](https://certcc.github.io/CERT-Guide-to-CVD/howto/coordination/response_pacing) analogous to the Prisoner's Dilemma.
One notable strategy for the Prisoner's Dilemma is *tit for tat* in which non-cooperation from one party in one round
can be met with non-cooperation from the opposite party in the next.
While MPCVD is usually much bigger than a toy two-player game, we feel it is necessary to encode the possibility that
non-cooperation will have downstream consequences.

!!! note ""

    Participants MAY decline to participate in future
    CVD cases involving parties with a history of violating previous embargoes.
