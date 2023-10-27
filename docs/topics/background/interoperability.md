# The Need for Interoperability in Coordinated Vulnerability Disclosure

The overall goal of our Vultron Protocol effort is to achieve *interoperability* among CVD process implementations according to the
broad definition of that term found in the 2004 report, [*Current Perspectives on Interoperability*](https://doi.org/10.1184/R1/6572852.v1) by Brownsword et al.:

!!! note inline "Brownsword et al. on *Interoperability*"

    The ability of a collection of communicating entities to (a) share
    specified information and (b) operate on that information according
    to an agreed operational semantics

This definition encompasses both (a) *syntactic* and (b) *semantic*
interoperability. The goal of this documentation is to lay the foundation for
the *semantic* interoperability of CVD processes across Participants.
*Syntactic* interoperability, in the form of message formats and the
like, is the focus of our ongoing effort.

Addressing *semantic interoperability* first is a deliberate choice.
If we were to go in the reverse order, we might wind up with systems that
exchange data quickly and accurately yet still fail to accomplish the
mutually beneficial outcomes that MPCVD sets out to achieve.
Carney et al. illustrate the importance of semantic interoperability in their 2005 report
[*Some Current Approaches to Interoperability*](https://doi.org/10.1184/R1/6584258.v1):

!!! quote "Carney et al. on semantic interoperability"

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

In this excerpt, replace the word "system" with the concept of a
"CVD Case Participant," and the need for semantic interoperability as a means of
achieving coordination in MPCVD becomes clear:

!!! quote "Paraphrasing Carney et al. in the context of CVD"

    \[...\] However, in the context of run-time interoperability, the
    situation is more complex, since there is need for some manner of
    universal agreement, so that a new CVD Participant can join, ad-hoc, some
    other group of CVD Participants \[in a CVD Case\]. The new CVD Case
    Participant must be able to usefully share data and meaning with those
    other CVD Case Participants, and those other Participants must be able to share data
    and meaning from an unfamiliar newcomer.

Elsewhere in the same [report](https://doi.org/10.1184/R1/6584258.v1), Carney et al.
write,

!!! quote "Carney et al. on the necessity of trust in interoperability"

    In the hoped-for context of unbounded systems of systems, trust in the
    actions and capabilities provided by interoperating parties is
    essential. Each party to an interaction must have, develop, or
    perceive a sense of whether the actions of interoperating parties can
    be trusted. This sense of trust is not Boolean (e.g., parties can be
    trusted to varying degrees), is context dependent (Party A can be
    trusted in a particular context but not in another), and is time
    sensitive (Party A can be trusted for a certain period). Further, the
    absence of trust-----distrust-----is less dangerous than misplaced
    trust: it is better to know that you cannot trust a particular party
    than to misplace trust in a party

The protocol we propose is intended to promote trust between MPCVD Participants both within an individual case as well
as over time and across cases.

## Objectives

The objectives of this documentation are as follows:

1. Provide a set of common primitives to serve as an ontological
    foundation for CVD process definitions across
    organizations.

2. Construct abstract workflows that support the inter-organizational
    coordination and synchronization required for the
    CVD process to
    be successful.

3. From those primitives and workflows, identify a set of message types
    needed for the CVD process to function.

4. Provide high-level requirements for the semantic content of those
    message types.

5. Explore options for the syntactic representation of those message
    types.
