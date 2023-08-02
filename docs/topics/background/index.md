# Introduction {#ch:intro}

The CVD process
addresses a human coordination problem that spans individuals and
organizations. As we wrote in [*The CERT* *Guide to Coordinated
Vulnerability Disclosure*](https://vuls.cert.org/confluence/display/CVD):

!!! quote "Excerpt from *The CERT Guide to Coordinated Vulnerability Disclosure*"

    Perhaps the simplest description of the CVD process is that it starts with at least one individual becoming aware of a vulnerability in a product.
    This discovery event immediately divides the world into two sets of people: those who know about the vulnerability, and those who don't.
    From that point on, those belonging to the set that knows about the vulnerability iterate on two questions:

    1.  What actions should I take in response to this knowledge?
    2.  Who else needs to know what, and when?
    
    The CVD process continues until the answers to these questions are "nothing," and "nobody."

### CVD *Is* MPCVD, and MPCVD *Is* CVD.

Any given CVD case
is made up of many individual disclosure events, for example,

-   from a Finder to one or more Vendors and/or Coordinators

-   from Vendors and Coordinators to other Vendors and Coordinators

-   from Finders, Vendors, and Coordinators to Deployers and the Public

In recent years, software supply chains have evolved such that software library and component vulnerabilities have 
become just as much a part of the everyday CVD process as vulnerabilities in Vendors' proprietary code. This means that
many CVD cases we encounter require coordination across multiple vendors. As a result, we find it decreasingly useful 
to differentiate between "traditional" (i.e., two-party) CVD and MPCVD. In this documentation, we use both terms
interchangeably.

$$CVD \iff MPCVD$$

Practically speaking, this means that readers should not infer from our
use of CVD in one place that we meant to exclude the multi-party scenario, nor that our
use of MPCVD implies the exclusion of the single-vendor CVD scenario. Instead, our intent is to
construct a protocol that adequately addresses the MPCVD scenario
where $N_{vendors} \geq 1$ and for which the "traditional" CVD case is merely
a special (and often simpler) case where $N_{vendors} = 1$.

### Context of Our Recent Work.

This documentation, in the context of recent CVD work at the
[CERT/CC](https://www.sei.cmu.edu/about/divisions/cert/index.cfm),
is one of four foundational documents aimed at increasing the
professionalization of the CVD process. The following is the full set of
foundational documents (thus far):

-   *The CERT Guide to Coordinated Vulnerability Disclosure* (the
    *CVD Guide*) in both its [original](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=503330)
    and [updated](https://vuls.cert.org/confluence/display/CVD) forms, provides a "field guide" perspective to the
    CVD process and its natural extension into MPCVD.

-   The [*Stakeholder-Specific Vulnerability Categorization*](https://github.com/CERTCC/SSVC)
    provides decision support for prioritizing vulnerability response activities
    closely associated with the CVD process.

-   [*A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure*](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513)
    describes a model that encompasses all possible CVD case histories into a set of measures and metrics for the 
    efficacy of CVD processes. That report is an expanded version of [*Are We Skillful or Just Lucky? Interpreting the Possible
    Histories of Vulnerability Disclosures*](https://dl.acm.org/doi/10.1145/3477431), an article published in the ACM Journal [Digital Threats: Research and Practice](https://dl.acm.org/journal/dtrap).

-   *Designing Vultron*, the report on which this documentation was based, proposes an abstract formal protocol for
    MPCVD, ties together various concepts from all three of the above.

Whereas the [*CVD Guide*](https://vuls.cert.org/confluence/display/CVD) offers a narrative description of both the CVD
process and the many scenarios one can expect to encounter as a Participant therein, in this documentation we provide an
additional layer of formality in the form of a *protocol* for MPCVD.

### What We Mean by *Protocol*.

We first define what we mean by our use of the term *protocol* by
providing a few common usages from the [Oxford English Dictionary](https://www.oed.com/).

!!! quote "Oxford English Dictionary on [*protocol*](https://www.oed.com/dictionary/protocol_n?tab=meaning_and_use)"
  
    (Computing and Telecommunications) A (usually standardized) set of
    rules governing the exchange of data between given devices, or the
    transmission of data via a given communications channel.

    (In extended use) the accepted or established code of behavior in
    any group, organization, or situation; an instance of this.

!!! question inline end "Why *Vultron*?"

    The working name for our protocol is *Vultron*, an homage to the
    fictional robot Voltron. In the Voltron animated series, a team of
    protectors joins forces to defend the universe from their adversaries.
    Their defensive mission requires a combination of independent defenders
    coordinating their efforts to achieve their goals. Like Voltron, our
    MPCVD protocol
    comprises a combination of humans and the technical processes and
    mechanisms that empower them. Together, those humans, processes, and
    mechanisms must function both individually and in coordination and
    cooperation with others to protect information systems and the people
    who depend on them from exploitation by adversaries.

Both usages are relevant to this effort.
First, insofar as we seek to scale the MPCVD process through the use of automation and software-augmented human
processes, we wish to propose a formal technical protocol that can serve as the basis of such technical tools.
The [Formal Protocol](/reference/formal_protocol) section of this documentation addresses this first definition in
specific detail after explicating its component parts and their interactions in 
[Report Management](/topics/process_models/rm), [Embargo Management](/topics/process_models/em), [Case State](/topics/process_models/cs),
and [Model Interactions](/topics/process_models/model_interactions).

Second, recognizing that MPCVD is primarily a coordination process among
human Participants with the goal of remediating extant vulnerabilities
in deployed information systems, a protocol must not only address the
technical formalities of communicating code but also extend to the
expected behaviors of the human Participants that rely on it. In this
second sense, we address the term *protocol* in these ways:

-   The *CVD Guide*
    offers a *narrative* protocol for practitioners to follow based on
    decades of accumulated experience and observation of the
    CVD process at
    the [CERT/CC]{acronym-label="CERT/CC"
    acronym-form="singular+short"} [@householder2017cert; @cert2019cvd].

-   The CS model
    from the Householder and Spring 2021 report [@householder2021state]
    offers a *prescriptive* protocol outlining the high-level goals of
    the CVD
    process, as derived from a first-principles approach to possible
    CVD case
    histories.

-   This report describes a *normative* protocol designed to structure
    and guide practitioners toward those goals.

To that end, we offer this report as a proposal for such an
MPCVD protocol.


## Goals

The overall goal of our MPCVD protocol effort is to achieve
*interoperability* among CVD process implementations according to the
broad definition of that term found in the SEI report, *Current
Perspectives on Interoperability* [@brownsword2004interoperability]:

!!! note inline "Interoperability"

    The ability of a collection of communicating entities to (a) share
    specified information and (b) operate on that information according
    to an agreed operational semantics

This definition encompasses both (a) *syntactic* and (b) *semantic*
interoperability. The goal of this report is to lay the foundation for
the *semantic* interoperability of CVD processes across Participants.
*Syntactic* interoperability, in the form of message formats and the
like, will be left as future work
(§[\[ch:future_work\]](#ch:future_work){reference-type="ref"
reference="ch:future_work"}).

Addressing *semantic interoperability* first is a deliberate choice. If
we were to go in the reverse order, we might wind up with systems that
exchange data quickly and accurately yet still fail to accomplish the
mutually beneficial outcomes that MPCVD sets out to achieve. Carney et al.
illustrate the importance of semantic interoperability in their report
*Some Current Approaches to
Interoperability* [@carney2005interoperability]:

!!! quote "Carney et al. on semantic interoperability in *Some Current Approaches to Interoperability*"

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
"CVD Case
Participant," and the need for semantic interoperability as a means of
achieving coordination in MPCVD becomes clear:

!!! quote "Paraphrasing Carney et al. in the context of CVD"

    \[...\] However, in the context of run-time interoperability, the
    situation is more complex, since there is need for some manner of
    universal agreement, so that a new CVD Participant can join, ad-hoc, some
    other group of CVD Participants \[in a CVD Case\]. The new CVD Case
    Participant must be able to usefully share data and meaning with those
    other CVD Case Participants, and those other Participants must be able to share data
    and meaning from an unfamiliar newcomer.

Elsewhere in the same report, Carney et al.
write [@carney2005interoperability],

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

The objectives of this report are as follows:

1.  Provide a set of common primitives to serve as an ontological
    foundation for CVD process definitions across
    organizations.

2.  Construct abstract workflows that support the inter-organizational
    coordination and synchronization required for the
    CVD process to
    be successful.

3.  From those primitives and workflows, identify a set of message types
    needed for the CVD process to function.

4.  Provide high-level requirements for the semantic content of those
    message types.


## Documentation Preview

MPCVD is comprised of independent Participants performing their own CVD-related processes.
Those processes can be represented by FSMs, specifically as DFAs. CVD processes (and
the DFAs representing them) can be decomposed hierarchically. 
We propose three main DFAs as the core of our MPCVD protocol:

1.  A [Report Management](/topics/process_models/rm) DFA represents each CVD Participant's engagement with a particular report
2.  An [Embargo Management](/topics/process_models/em) DFA negotiates and establishes the timing of future disclosures and publications
3.  A [Case State](/topics/process_models/cs) DFA tracks the events in {== Table [\[tab:cs_transitions\]](#tab:cs_transitions){reference-type="ref"
    reference="tab:cs_transitions"} ==}, as originally described in the {== Householder and Spring 2021 report [@householder2021state] ==}.

[Model Interactions](/topics/process_models/model_interactions) contains a discussion of the interactions
among these three state machine models.

However, a set of agents independently executing processes is not coordinated, and if they are not coordinated, then whatever they are
doing does not deserve the name CVD. Hence, there is a need for a protocol to describe the interactions necessary to coordinate these processes.
Communicating FSMs provide a formal way to define a communications protocol, which
coordinates the activities of independent DFAs through the interchange (e.g., sending and
receiving) of messages {== [@brand1983communicating] ==}.
We map our multiple DFA model onto a formal protocol definition in [Formal Protocol](/reference/formal_protocol).

However, an MPCVD
protocol needs to do more than just provide formally defined
communication mechanisms. It also needs to normalize the expected
behaviors and activities that the communication protocol enables. In
this sense, our protocol expands upon {== ISO/IEC 29147:2018 *Vulnerability
Disclosure*, ISO/IEC 30111:2019 *Vulnerability Handling Processes*, and
ISO/IEC TR 5895:2022 ==}, which, taken together, provide a high-level
normative standard for CVD activities.

Developed in response to the growing complexity of video game
Non-Player Character (NPC) Artificial Intelligence (AI) FSMs, Behavior Trees
offer a way to organize and describe agent behaviors in a
straightforward, understandable way. Using Behavior Trees, agent
processes can be modeled as sets of behaviors (e.g., pre-conditions,
actions, and post-conditions) and the logic that joins them together.
Today, Behavior Trees are used in video game software to develop
realistic NPCs and in robotics to create reactive and adaptive behaviors from autonomous
agents. Behavior Trees offer a high potential for automating complex
tasks through a hierarchical decomposition of the logic and actions
required to complete those tasks.

The behaviors we are interested in modeling are the various
CVD activities described in the [*CVD Guide*](https://vuls.cert.org/confluence/display/CVD) (e.g., find contacts, send
reports, validate reports, prioritize reports, create fixes, publish
reports, publish fixes, deploy fixes).
{== Chapter
[\[ch:behavior_trees\]](#ch:behavior_trees){reference-type="ref"
reference="ch:behavior_trees"} ==} uses Behavior Trees to describe
MPCVD Participant activities and their interactions with the [formal protocol](/reference/formal_protocol).

Additional [implementation notes](/topics/implementation_notes), including a simplified case data model, are provided.
Future work is discussed in [Future Work](/topics/future_work).
{== Our conclusion is in Chapter
[\[ch:conclusion\]](#ch:conclusion){reference-type="ref"
reference="ch:conclusion"}. ==}

Appendices are included to provide connections to closely related work:
In Appendix
[\[app:ssvc_mpcvd_protocol\]](#app:ssvc_mpcvd_protocol){reference-type="ref"
reference="app:ssvc_mpcvd_protocol"}, we provide a mapping between the
MPCVD protocol
and relevant portions of the SSVC, a vulnerability response prioritization
model also developed by the [CERT/CC]{acronym-label="CERT/CC"
acronym-form="singular+short"}. Appendix
[\[app:iso_crosswalk\]](#app:iso_crosswalk){reference-type="ref"
reference="app:iso_crosswalk"} contains a detailed crosswalk of our
protocol with ISO/IEC 29147:2018 *Vulnerability Disclosure*, ISO/IEC
30111:2019 *Vulnerability Handling Processes*, and ISO/IEC TR 5895:2022
*Multi-party coordinated vulnerability disclosure and handling*.
Appendix [\[app:em_icalendar\]](#app:em_icalendar){reference-type="ref"
reference="app:em_icalendar"} maps concepts from the
EM process onto the
`iCalendar` protocol.

A list of acronyms is provided at the end of the report.

