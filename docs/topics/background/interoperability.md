---
description: >
  Why organizations coordinating a vulnerability case need shared meaning, not
  only a shared message format, and what this documentation gives you toward it.
stakeholder_type: [cvd-practitioner, platform-developer, process-researcher]
level: 200
---

# The Need for Interoperability in Coordinated Vulnerability Disclosure

A Coordinated Vulnerability Disclosure (CVD) case with five Participants usually runs on five systems that cannot talk to each other.
The reporter submits through one vendor's portal, the coordinator tracks the case in its own tool, and a second vendor works it in an internal ticket queue.
A person relays every status change: from one system into an encrypted email, and from the email into the next system.
When another vendor joins mid-case, someone brings it up to date by hand.

This page explains why fixing that takes more than a common message format, and what this documentation gives you toward fixing it.

---

## Exchanging data is not enough

Suppose those five systems adopted a common file format tomorrow.
They could exchange case records, but each would still interpret them by its own rules.
One vendor's "accepted" means it will fix the vulnerability; another's means only that it read the report.
One system treats an embargo end date as firm; another treats it as a target.
The data moves, and the case still falls apart.

Interoperability research names the two halves of this problem.
*Syntactic* interoperability is agreement on the form of the data.
*Semantic* interoperability is agreement on what the data means and what each party does with it.
Brownsword et al. define interoperability to require both:

!!! quote "Brownsword et al., [*Current Perspectives on Interoperability*](https://doi.org/10.1184/R1/6572852.v1){:target="_blank"} (2004)"

    The ability of a collection of communicating entities to (a) share
    specified information and (b) operate on that information according
    to an agreed operational semantics

Vultron addresses semantic interoperability first, deliberately.
Systems that exchange data quickly and accurately, but act on it differently, would still fail to reach the outcomes a case exists for.

---

## A newcomer must be able to join

CVD cases are assembled on the fly.
The Participants are not known in advance, and new ones join as the case uncovers more affected products.
So the agreement on meaning cannot be negotiated pairwise before the case starts.
It has to exist already, in a form any newcomer can adopt.

Carney et al. describe this as the harder, run-time form of interoperability.
Read "system" as "CVD case Participant" and the passage describes a multi-party case:

!!! quote "Carney et al., [*Some Current Approaches to Interoperability*](https://doi.org/10.1184/R1/6584258.v1){:target="_blank"} (2005)"

    There is a limited number of ways that agreements on meaning can be
    achieved. In the context of design-time interoperability, semantic
    agreements are reached in the same manner as interface agreements
    between the constituent systems... However, in the context of run-time
    interoperability, the situation is more complex, since there is need
    for some manner of universal agreement, so that a new system can join,
    ad-hoc, some other group of systems. The new system must be able to
    usefully share data and meaning with those other systems, and those
    other systems must be able to share data and meaning from an
    unfamiliar newcomer.

---

## Trust varies by party, context, and time

A vendor may trust a coordinator with embargoed details but not with an unpatched exploit.
It may trust a reporter it has worked with for years more than one it has never heard from.
And trust earned in one case can be lost in the next.

Interoperation among parties who do not fully trust each other has to account for this.
The same report makes the point:

!!! quote "Carney et al. on the necessity of trust in interoperability"

    In the hoped-for context of unbounded systems of systems, trust in the
    actions and capabilities provided by interoperating parties is
    essential. Each party to an interaction must have, develop, or
    perceive a sense of whether the actions of interoperating parties can
    be trusted. This sense of trust is not Boolean (e.g., parties can be
    trusted to varying degrees), is context dependent (Party A can be
    trusted in a particular context but not in another), and is time
    sensitive (Party A can be trusted for a certain period). Further, the
    absence of trust—distrust—is less dangerous than misplaced
    trust: it is better to know that you cannot trust a particular party
    than to misplace trust in a party

The Vultron Protocol is meant to build trust between Participants within a single case, and over time across cases.

---

## What this documentation gives you

Each part of the documentation supplies one piece of the shared agreement a newcomer needs.

| What you get | Where it is |
|---|---|
| Common primitives, so that "accepted" or "embargo active" means the same thing in every Participant's system | [Vultron Process Models](../process_models/index.md) |
| Workflows for the coordination and synchronization across organizations that a case needs | [Behavior Logic](../behavior_logic/index.md) |
| The set of message types those workflows exchange | [Message Types](../../reference/messages/index.md) |
| What each message means to the Participant who receives it | [Message Semantics](../message_semantics.md) |
| A concrete wire format for those messages, built on ActivityStreams 2.0 | [Vultron and ActivityPub](../../howto/activitypub/index.md) |
