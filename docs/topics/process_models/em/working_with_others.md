---
stakeholder_type: [cvd-practitioner]
level: 300
page_type: explanation
description: >
  Adding Participants to a case under embargo.
---

# Adding Participants to an Embargoed Case

{% include-markdown "../../../includes/specification_governs.md" %}

Here we describe who to add to an embargoed case, and when to add them.

Multi-party scheduling can be difficult, as anyone who has tried to schedule a meeting with many attendees knows.
It becomes even harder when the schedule must also fit the work completion schedules for an MPCVD case.

In [Default Embargoes](./defaults.md), we gave a heuristic to resolve multiple embargo proposals: *The Shortest Embargo Proposed Wins*.
More specifically, we recommended that Participants *accept* the earliest proposed end date.
They then immediately propose and evaluate the other proposals as potential revisions.
This principle applies to all MPCVD cases, even at their start.

## Start Early, Start Small

Embargo negotiations can become contentious in larger cases.
Many MPCVD cases grow over time.
It is usually easier to establish an embargo with a smaller group than with a larger one.

Conflict resolution by consensus agreement is satisfactory if it works.
Participants who have already agreed to an embargo sometimes choose who else to add to it.
In these scenarios, the existing consensus can strongly influence the new Participant to consent to the existing agreement.

In other words, one approach is usually better than the other.
The better approach is to present an already-accepted embargo to new Participants and get their agreement, and then possibly revise the embargo.
The worse approach is to wait for a large multi-party negotiation to succeed before any embargo exists.

!!! tip inline end "See also"

    [ISO/IEC 29147:2018](https://www.iso.org/standard/72311.html){:target="_blank"}

However, when consensus fails, the group can appoint a case lead to resolve conflicts.
Such scenarios are often an opportunity to engage a third-party Coordinator.

Therefore,

!!! note ""

    Participants SHOULD attempt to establish an embargo as early in the process of handling the case as possible.

!!! note ""

    Participants SHOULD follow consensus agreement to decide embargo terms.

!!! note ""

    When consensus fails to reach agreement on embargo terms, Participants MAY appoint a case lead to resolve conflicts.

!!! note ""

    Participants MAY engage a third-party Coordinator to act as a neutral third-party case lead to resolve conflicts between Participants during the course of handling a case.

## Who to Invite

By definition, the Finder/Reporter is a Participant in every CVD case, because they know about the vulnerability.
Additional Participants are usually in one of three categories:

!!! note ""

    All known Vendors of affected software SHOULD be included as Participants.

!!! note ""

    Third-party Coordinators MAY be included as Participants.

!!! note ""

    Other parties MAY be included as Participants when necessary and appropriate.

!!! example "Examples of Other Participants"

    Examples of other Participants we have observed in past cases include

    - Deployers
    - Subject matter experts
    - Government agencies with relevant regulatory oversight or critical infrastructure protection responsibilities.

## Adding Participants to an Existing Embargo

When Participants add a new Participant to a case with an existing embargo, the new Participant might have to accept the embargo before they receive the report.
[Embargo Lifecycle](../../behavior_logic/use-cases/embargo-lifecycle.md) explains how the protocol tracks the acceptance of each Participant.
[§9 Participant Embargo Consent (PEC) State Machine in the Vultron Protocol Specification](../../../reference/vultron-spec/tracking-models.md#9-participant-embargo-consent-pec-state-machine-n) specifies it.

!!! note ""

    When inviting a new Participant to a case with an existing embargo, the inviting Participant SHALL propose the existing embargo to the invited Participant.

!!! note ""

    A newly invited Participant to a case with an existing embargo SHOULD accept the existing embargo.

!!! note ""

    The inviting Participant SHOULD NOT share the vulnerability report with the newly invited Participant unless the new Participant has accepted the existing embargo.

!!! note ""

    The inviting Participant MAY interpret the potential Participant's default embargo contained in their published vulnerability disclosure policy in accordance with the default acceptance strategies listed in [Default Embargoes](./defaults.md).

!!! note ""

    A newly invited Participant to a case with an existing embargo MAY propose a revision after accepting the existing embargo.

## When to Invite Participants

In MPCVD, there are practical considerations about *when* to notify individual Participants.
The primary factor in these decisions is how the *Active* embargo interacts with the existing disclosure policy of the potential Participant.
That policy can be explicit or implicit.

### Participants with Disclosure Policies Shorter Than an Existing Embargo

A potential Participant can have a known default disclosure policy that is *shorter* than an extant embargo.
To add this Participant, the other Participants can choose from these options:

1. Shorten the existing embargo to match the policy of the potential Participant.

2. Propose the existing embargo to the potential Participant.
    When they accept it, share the report with them.

3. Wait to notify the potential Participant until their default policy aligns with the existing embargo.

4. Do not include the potential Participant in the embargo at all.

!!! example "Example: A Vendor with a short default embargo"

    Say a Vendor has a seven-day maximum public disclosure policy.
    A case has an existing embargo that ends in three weeks.
    The Participants in that case might choose to notify that Vendor two weeks from now.
    Then even the default disclosure timeline of the Vendor stays compatible with the extant embargo.

!!! note ""

    Participants with short default embargo policies SHOULD consider accepting longer embargoes in MPCVD cases.

!!! note ""

    Participants in an MPCVD case MAY delay notifying potential Participants with short default embargo policies until their policy aligns with the agreed embargo.

### Participants with Disclosure Policies Longer Than an Existing Embargo

Similarly, a potential Participant can have a known default disclosure policy that is *longer* than an extant embargo.
To add this Participant, the other Participants can choose from these options:

1. Make the existing embargo longer to match the policy of the potential Participant.

2. Propose the existing embargo to the potential Participant.
    When they accept it, share the report with them.

3. Do not include the potential Participant in the embargo at all.

A Vendor can have a *longer* default policy than the existing embargo.
It is still better to give that Vendor as much lead time as possible, *even* if the embargo cannot extend to their preferred timing.

!!! note ""

    In the interest of receiving the report in the first place, potential Participants with a longer default policy than an existing case SHOULD accept the embargo terms offered.

!!! note ""

    After accepting an existing embargo, newly invited Participants with a longer default policy than an existing case MAY propose a revision to the existing embargo, if desired, to accommodate their preferences.

!!! note ""

    Existing Participants MAY *accept* or *reject* such a proposed revision as they see fit.

!!! note ""

    Participants in a case with an existing embargo SHOULD notify Vendors with a longer default embargo policy.

!!! note ""

    Participants in a case with an existing embargo MAY choose to extend the embargo to accommodate a newly added Participant.

### Untrustworthy Participants

Unfortunately, not all potential CVD Participants are equally trustworthy with vulnerability information.

!!! example "Examples of Untrustworthy Participants"

    We can provide a few examples of potentially untrustworthy Participants:
    
    - A Participant might have sub-par operational security, or even sub-par business practices.
    As a result, adversaries often find out about vulnerabilities in their products before the end of an embargo period.
    - Participants might be subject to regulatory regimes.
    In these regimes, the law requires them to share known vulnerabilities with government agencies that have oversight responsibilities.
    Depending on the jurisdiction, these agencies might not be bound by the same embargoes as the other Participants in the case.
    - The Participants in a case might consider a government agency to be an adversary itself.
    So they do not trust that agency with non-public vulnerability information.

    In these or similar scenarios, these concerns might cause the exclusion of otherwise trustworthy Participants from an embargo.

!!! note ""

    Participants that are known to leak or provide vulnerability information to adversaries either as a matter of policy or historical fact SHOULD be treated similar to Participants with brief disclosure policies.

!!! tip "My Adversary Is *Not Necessarily* Your Adversary"

    Trustworthiness has a strong subjective component.
    Individual perspectives on who is or is not trustworthy can be very different.
    *Adversary* is not a universally agreed-upon category.
    So each Participant decides the definition of *adversary* in the text above.

In the maximal interpretation of the text above, untrustworthy Participants find out only when the vulnerability report is published.
This is equivalent to treating them like a Participant with a default zero-day maximum embargo policy.

### Coordinators

Third-party Coordinators are Participants who are neither Finders nor Vendors.
They often have an important role in MPCVD cases.
This is especially true for cases with broad impact across the software supply chain, or with acute impacts on critical infrastructure or public safety.

Most Coordinators try to be consistent in their MPCVD practices.
They have well-documented disclosure policies and significant histories of handling previous cases.
All of these factors support the inclusion of third-party Coordinators in CVD cases of sufficient complexity, impact, or importance.

### Other Parties

Some Participants in CVD have their own policies about notification.
These policies prohibit the notification of any party that cannot directly help develop a fix for a particular vulnerability.
Typically, these policies say "only Vendors of affected products", or give a similar restriction.

The CERT/CC has been a third-party Coordinator in numerous cases.
Its position is that this approach can be appropriate for straightforward scenarios.
An example is a scenario in which a Vendor is in direct contact with their downstream Vendors and can coordinate the response within that community.

However, this approach is not sufficient in some cases, such as the following:

- Vulnerabilities affect a broad spectrum of Vendors and products.
    This is especially true when cases cross industry sectors, or include Participants that have very different operational tempos or software delivery models.

- Vulnerabilities affect systems deployed in high-impact niches, such as critical infrastructure, public safety, and national security.

- Outside expertise is necessary to understand the implications or impact of a vulnerability beyond the participating Vendors.
    Sometimes the most knowledgeable parties work for someone else.

## Consequences of Non-Compliance

Over multiple cases and time, MPCVD can be seen as an [iterated game](https://certcc.github.io/CERT-Guide-to-CVD/howto/coordination/response_pacing){:target="_blank"} similar to the Prisoner's Dilemma.
One notable strategy for the Prisoner's Dilemma is *tit for tat*.
In this strategy, when one party does not cooperate in one round, the opposite party can refuse to cooperate in the next round.
MPCVD is usually much bigger than a toy two-player game.
But we think that it is necessary to encode the possibility that non-cooperation will have downstream consequences.

!!! note ""

    Participants MAY decline to participate in future CVD cases involving parties with a history of violating previous embargoes.

## Doing It on the Wire

- [How to Invite an Actor to a Case](../../../howto/activitypub/activities/invite_actor.md) — invite a new Participant, who is offered the existing embargo.
- [How to Establish an Embargo](../../../howto/activitypub/activities/establish_embargo.md) — propose, accept and activate an embargo.
- [How to Revise or Terminate an Embargo](../../../howto/activitypub/activities/manage_embargo.md) — propose the shorter terms a new Participant needs as a revision, or end the embargo.
