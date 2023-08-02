# Introduction {#ch:intro}

The CVD process
addresses a human coordination problem that spans individuals and
organizations. As we wrote in *The CERT* *Guide to Coordinated
Vulnerability Disclosure* [@householder2017cert; @cert2019cvd],

> Perhaps the simplest description of the CVD process is that it starts with at least
> one individual becoming aware of a vulnerability in a product. This
> discovery event immediately divides the world into two sets of people:
> those who know about the vulnerability, and those who don't. From that
> point on, those belonging to the set that knows about the
> vulnerability iterate on two questions:
>
> 1.  What actions should I take in response to this knowledge?
>
> 2.  Who else needs to know what, and when?
>
> The CVD process
> continues until the answers to these questions are "nothing," and
> "nobody."

### CVD *Is* MPCVD, and MPCVD *Is* CVD.

Any given CVD case
is made up of many individual disclosure events, for example,

-   from a Finder to one or more Vendors and/or Coordinators

-   from Vendors and Coordinators to other Vendors and Coordinators

-   from Finders, Vendors, and Coordinators to Deployers and the Public

In recent years, software supply chains have evolved such that software
library and component vulnerabilities have become just as much a part of
the everyday CVD
process as vulnerabilities in Vendors' proprietary code. This means that
many CVD cases we
encounter require coordination across multiple vendors. As a result, we
find it decreasingly useful to differentiate between "traditional"
(i.e., two-party) CVD and MPCVD. In this report, we use both terms
interchangeably.

$$CVD \iff MPCVD$$

Practically speaking, this means that readers should not infer from our
use of CVD in one
place that we meant to exclude the multi-party scenario, nor that our
use of MPCVD
implies the exclusion of the single-vendor CVD scenario. Instead, our intent is to
construct a protocol that adequately addresses the
MPCVD scenario
where $N_{vendors} \geq 1$ and for which the "traditional"
CVD case is merely
a special (and often simpler) case where $N_{vendors} = 1$.

### Context of Our Recent Work.

This report, in the context of recent CVD work at the
[CERT/CC]{acronym-label="CERT/CC" acronym-form="singular+short"}, is one
of four foundational documents aimed at increasing the
professionalization of the CVD process. The following is the full set of
foundational documents (thus far):

-   *The CERT Guide to Coordinated Vulnerability Disclosure* (the
    *CVD Guide*) in
    both its original [@householder2017cert] and updated
    forms [@cert2019cvd], provides a "field guide" perspective to the
    CVD process and
    its natural extension into MPCVD.

-   *A Stakeholder-Specific Vulnerability Categorization*
     [@spring2019ssvc; @spring2020ssvc; @spring2021ssvc] provides
    decision support for prioritizing vulnerability response activities
    closely associated with the CVD process.

-   *A State-Based Model for Multi-Party Coordinated Vulnerability
    Disclosure* [@householder2021state] describes a model that
    encompasses all possible CVD case histories into a set of measures
    and metrics for the efficacy of CVD processes. That report is an expanded
    version of "Are We Skillful or Just Lucky? Interpreting the Possible
    Histories of Vulnerability Disclosures," an article published in the
    ACM Journal of
    DTRAP [@householder2021skillful].

-   This report, which proposes an abstract formal protocol for
    MPCVD, ties
    together various concepts from all three of the above.

Whereas the *CVD
Guide* offers a narrative description of both the
CVD process and the
many scenarios one can expect to encounter as a Participant therein, in
this report, we provide an additional layer of formality in the form of
a *protocol* for MPCVD.

### What We Mean by *Protocol*.

We first define what we mean by our use of the term *protocol* by
providing a few common usages from the Oxford English Dictionary
 [@oxford2021protocol].

-   (Computing and Telecommunications) A (usually standardized) set of
    rules governing the exchange of data between given devices, or the
    transmission of data via a given communications channel.

-   (In extended use) the accepted or established code of behavior in
    any group, organization, or situation; an instance of this.

Both usages are relevant to this report. First, insofar as we seek to
scale the MPCVD
process through the use of automation and software-augmented human
processes, we wish to propose a formal technical protocol that can serve
as the basis of such technical tools. Chapter
[\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
reference="sec:formal_protocol"} addresses this first definition in
specific detail after explicating its component parts and their
interactions in Chapters
[\[sec:report_management\]](#sec:report_management){reference-type="ref"
reference="sec:report_management"},
[\[ch:embargo\]](#ch:embargo){reference-type="ref"
reference="ch:embargo"},
[\[sec:model\]](#sec:model){reference-type="ref" reference="sec:model"},
and [\[ch:interactions\]](#ch:interactions){reference-type="ref"
reference="ch:interactions"}.

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

### Why *Vultron*?

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

### Version Numbering Scheme.

While we have not yet mapped out a future release schedule, in
anticipation of future revisions, we have chosen a semantic versioning
scheme for the Vultron protocol. Specifically, Vultron versions will be
assigned according to the format *MAJOR.MINOR.MICRO*, where

-   *MAJOR* represents the zero-indexed major version for the release.

-   *MINOR* represents a zero-indexed counter for minor releases that
    maintain compatibility with their MAJOR version.

-   *MICRO* represents an optional zero-indexed micro-version (patch)
    counter for versions that update a MINOR version.

Trailing zero values may be omitted (e.g., `3.1` and `3.1.0` denote the
same version, similarly `5` and `5.0`). It may be useful at some point
to use pre-release tags such as *-alpha*, *-beta*, *-rc* (with optional
zero-indexed counters as needed), but we reserve that decision until
their necessity becomes clear. The same goes for build-specific tags;
while we do not currently have a use for them, we do not rule out their
future use.

Because of the early nature of the current version of the protocol (),
as of this writing, no backward compatibility commitments are made or
implied within the `0.x` versions. We anticipate this commitment will
change as we get closer to a major release.

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

> \[...\] However, in the context of run-time interoperability, the
> situation is more complex, since there is need for some manner of
> universal agreement, so that a new CVD Participant can join, ad-hoc, some
> other group of CVD Participants \[in a
> CVD Case\]. The
> new CVD Case
> Participant must be able to usefully share data and meaning with those
> other CVD Case
> Participants, and those other Participants must be able to share data
> and meaning from an unfamiliar newcomer.

Elsewhere in the same report, Carney et al.
write [@carney2005interoperability],

> In the hoped-for context of unbounded systems of systems, trust in the
> actions and capabilities provided by interoperating parties is
> essential. Each party to an interaction must have, develop, or
> perceive a sense of whether the actions of interoperating parties can
> be trusted. This sense of trust is not Boolean (e.g., parties can be
> trusted to varying degrees), is context dependent (Party A can be
> trusted in a particular context but not in another), and is time
> sensitive (Party A can be trusted for a certain period). Further, the
> absence of trust-----distrust-----is less dangerous than misplaced
> trust: it is better to know that you cannot trust a particular party
> than to misplace trust in a party

The protocol we propose is intended to promote trust between
MPCVD
Participants both within an individual case as well as over time and
across cases.

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

## What Does "Success" Mean in CVD

We take as a base set of criteria the ordering preferences given in the
Householder and Spring 2021 report [@householder2021state]. While we
incorporate this model fully in Chapter
[\[sec:model\]](#sec:model){reference-type="ref" reference="sec:model"},
some notation is necessary to proceed here. The CS model is built on the idea that there are
six events of significance in the lifespan of every vulnerability:
Vendor Awareness, Fix Ready, Fix Deployed, Public Awareness, Exploit
Public, and Attacks Observed. Brief descriptions of those events are
listed in Table
[\[tab:cs_transitions\]](#tab:cs_transitions){reference-type="ref"
reference="tab:cs_transitions"}.

The Householder and Spring 2021 report defines a set of 12 ordering
preferences over these 6 events [@householder2021state]. We present them
in roughly descending order of desirability according to the partial
order developed in that report [@householder2021state]. Items closer to
the top of the list are indicators of CVD skill. The symbol $\prec$ is read as
*precedes*.

Fix Deployed Before Public Awareness ($\mathbf{D} \prec \mathbf{P}$).

:   For a fix to be deployed prior to public awareness, a lot has to go
    right in the CVD process: The vendor has to know about
    the vulnerability, create a fix, and deploy it-----all without
    public knowledge-----and has to achieve all that prior to any
    exploits being published or attacks becoming known to the public.
    Furthermore, it requires that the Vendor has the capability to
    deploy fixes without intervention by the system owner or user, which
    is a rare engineering feat unattainable by many software supply
    chains. More often, fix deployment ($\mathbf{D}$) requires users
    and/or system owners (Deployers) to take action. The need to inform
    Deployers implies a need for public awareness of the vulnerability,
    making this criteria impossible to achieve in those scenarios.

Fix Ready Before Public Awareness ($\mathbf{F} \prec \mathbf{P}$).

:   Deployers (i.e., the public) can take no action until a fix is
    ready. Because public awareness also implies adversary awareness,
    the vendor-adversary race becomes even more critical when this
    condition is not met. Only Vendors who can receive *and act* on
    vulnerability reports---whether those reports originate from inside
    or outside of the organization---are able to achieve this goal.

Fix Deployed Before Exploit Public ($\mathbf{D} \prec \mathbf{X}$).

:   Deploying a fix before an exploit is made public helps reduce the
    net risk to end users.

Fix Deployed Before Attacks Observed ($\mathbf{D} \prec \mathbf{A}$).

:   Attacks occurring before a fix has been deployed are when there's
    maximum risk to users; therefore, we wish to avoid that situation.

Fix Ready Before Exploit Public ($\mathbf{F} \prec \mathbf{X}$).

:   Exploit publication prior to fix readiness represents a period of
    increased threat to users since it means that attackers can exploit
    the vulnerability even if they lack exploit development skills. When
    fixes are ready before exploits are made public, defenders are
    better positioned to protect their users.

Vendor Awareness Before Public Awareness ($\mathbf{V} \prec \mathbf{P}$).

:   Public awareness prior to vendor awareness can cause increased
    support costs for vendors at the same time they are experiencing
    increased pressure to prepare a fix.

Fix Ready Before Attacks Observed ($\mathbf{F} \prec \mathbf{A}$).

:   As in the case with published exploits, when fixes exist before
    attacks are observed, defenders are in a substantially better
    position to protect their users.

Public Awareness Before Exploit Public ($\mathbf{P} \prec \mathbf{X}$).

:   There is broad agreement that it is better for the public to find
    out about a vulnerability via a CVD process rather than because someone
    published an exploit for any adversary to use.

Exploit Public Before Attacks Observed ($\mathbf{X} \prec \mathbf{A}$).

:   This criterion is not about whether exploits should be published or
    not. It is about whether we should prefer histories in which
    exploits are published *before* attacks happen over histories in
    which exploits are published *after* attacks happen. Because
    attackers have more advantages in the latter case than the former,
    histories in which $\mathbf{X} \prec \mathbf{A}$ are preferable to
    those in which $\mathbf{A} \prec \mathbf{X}$.

Public Awareness Before Attacks Observed ($\mathbf{P} \prec \mathbf{A}$).

:   Similar to the exploit case above, public awareness via
    CVD is
    generally preferred over public awareness resulting from incident
    analysis that results from attack observations.

Vendor Awareness Before Exploit Public ($\mathbf{V} \prec \mathbf{X}$).

:   If public awareness of the vulnerability prior to vendor awareness
    is bad, then a public exploit is at least as bad because it
    encompasses the former and makes it readily evident that adversaries
    have exploit code available for use.

Vendor Awareness Before Attacks Observed ($\mathbf{V} \prec \mathbf{A}$).

:   Attacks prior to vendor awareness represent a complete failure of
    the vulnerability remediation process because they indicate that
    adversaries are far ahead of defenders.

Taken together, these twelve ordering preferences constitute the minimum
set of outcomes we hope to emerge from the protocol proposed in this
report.

## Report Preview

MPCVD is
comprised of independent Participants performing their own
CVD-related
processes. Those processes can be represented by
FSMs, specifically as
DFAs.
CVD processes (and
the DFAs representing
them) can be decomposed hierarchically. We propose three main
DFAs as the core of
our MPCVD
protocol:

1.  A RM
    DFA represents
    each CVD
    Participant's engagement with a particular report (Chapter
    [\[sec:report_management\]](#sec:report_management){reference-type="ref"
    reference="sec:report_management"}).

2.  An EM
    DFA negotiates
    and establishes the timing of future disclosures and publications
    (Chapter [\[ch:embargo\]](#ch:embargo){reference-type="ref"
    reference="ch:embargo"}).

3.  A CS
    DFA tracks the
    events in Table
    [\[tab:cs_transitions\]](#tab:cs_transitions){reference-type="ref"
    reference="tab:cs_transitions"}, as originally described in the
    Householder and Spring 2021 report [@householder2021state] and
    summarized in Chapter
    [\[sec:model\]](#sec:model){reference-type="ref"
    reference="sec:model"} of this report.

Chapter [\[ch:interactions\]](#ch:interactions){reference-type="ref"
reference="ch:interactions"} contains a discussion of the interactions
among these three state machine models.

However, a set of agents independently executing processes is not
coordinated, and if they are not coordinated, then whatever they are
doing does not deserve the name CVD. Hence, there is a need for a protocol to
describe the interactions necessary to coordinate these processes.
Communicating FSMs
provide a formal way to define a communications protocol, which
coordinates the activities of independent DFAs through the interchange (e.g., sending and
receiving) of messages [@brand1983communicating]. We map our multiple
DFA model onto a
formal protocol definition in Chapter
[\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
reference="sec:formal_protocol"}.

However, an MPCVD
protocol needs to do more than just provide formally defined
communication mechanisms. It also needs to normalize the expected
behaviors and activities that the communication protocol enables. In
this sense, our protocol expands upon ISO/IEC 29147:2018 *Vulnerability
Disclosure*, ISO/IEC 30111:2019 *Vulnerability Handling Processes*, and
ISO/IEC TR 5895:2022, which, taken together, provide a high-level
normative standard for CVD
activities [@ISO29147; @ISO30111; @ISO5895].

Developed in response to the growing complexity of video game
NPC
AI
FSMs, Behavior Trees
offer a way to organize and describe agent behaviors in a
straightforward, understandable way. Using Behavior Trees, agent
processes can be modeled as sets of behaviors (e.g., pre-conditions,
actions, and post-conditions) and the logic that joins them together.
Today, Behavior Trees are used in video game software to develop
realistic NPCs and in
robotics to create reactive and adaptive behaviors from autonomous
agents. Behavior Trees offer a high potential for automating complex
tasks through a hierarchical decomposition of the logic and actions
required to complete those tasks.

The behaviors we are interested in modeling are the various
CVD activities
described in the *CVD Guide* (e.g., find contacts, send
reports, validate reports, prioritize reports, create fixes, publish
reports, publish fixes, deploy fixes) [@householder2017cert]. Chapter
[\[ch:behavior_trees\]](#ch:behavior_trees){reference-type="ref"
reference="ch:behavior_trees"} uses Behavior Trees to describe
MPCVD Participant
activities and their interactions with the MPCVD protocol proposed in Chapter
[\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
reference="sec:formal_protocol"}.

Additional implementation notes, including a simplified case data model,
can be found in Chapter
[\[ch:implementation notes\]](#ch:implementation notes){reference-type="ref"
reference="ch:implementation notes"}. Chapter
[\[ch:future_work\]](#ch:future_work){reference-type="ref"
reference="ch:future_work"} covers future work not addressed here. Our
conclusion is in Chapter
[\[ch:conclusion\]](#ch:conclusion){reference-type="ref"
reference="ch:conclusion"}.

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

## Terms and Definitions {#sec:terms_and_definitions}

Throughout this report, we refer to CVD Roles from the *CERT Guide to Coordinated
Vulnerability Disclosure* [@householder2017cert; @cert2019cvd]:

Finder.

:   The individual or organization that identifies the vulnerability

Reporter.

:   The individual or organization that notifies the vendor of the
    vulnerability

Vendor (Supplier).

:   The individual or organization that created or maintains the
    vulnerable product

Deployer (User).

:   The individual or organization that must deploy a patch or take
    other remediation action

Coordinator.

:   An individual or organization that facilitates the coordinated
    response process

The *Vendor* role is synonymous with the *Supplier* role as it appears
in SSVC Version 2
 [@spring2021ssvc]. The *Deployer* role is synonymous with the *User*
role in ISO/IEC 29147:2018 and ISO/IEC
30111:2019 [@ISO29147; @ISO30111], while the other roles are named
consistent with those standards.

We also add a new role in this report, which we expect to incorporate
into a future version of the *CVD Guide*:

Exploit Publisher.

:   An individual or organization that publishes exploits (Exploit
    Publishers might be the same as Finders, Reporters, Coordinators, or
    Vendors, but this is not guaranteed. For example, Vendors that
    produce tools for Cybersecurity Red Teams might play a combination
    of roles: Finder, Reporter, Vendor, Coordinator, and/or Exploit
    Publisher.)

Finally, we have a few additional terms to define:

CVD Case.

:   The unit of work for the overall CVD process for a specific vulnerability
    spanning the individual CVD Case Participants and their
    respective RM
    and EM processes

CVD Case Participant.

:   Finder, Vendor, Coordinator, Deployer, etc., as defined above

Vulnerability Report.

:   The unit of work for an individual Case Participant's
    RM process

A diagram showing the relationship between CVD Cases, Participants, and Reports can be
found in Figure
[\[fig:mpcvd_uml_class_diagram\]](#fig:mpcvd_uml_class_diagram){reference-type="ref"
reference="fig:mpcvd_uml_class_diagram"}.

## Notation {#sec:notation}

Before we proceed, we need to formally define our terms. In all of these
definitions, we take the standard Zermelo-Fraenkel set theory. We adopt
the following notation:

!!! info "Set Theory Symbols"

    | Symbol | Meaning |
    | :--- | :--- |
    | $\{ \dots \}$ | depending on the context: (1) an ordered set in which the items occur in that sequence, or (2) a tuple of values |
    | \|$x$\| | the count of the number of elements in a list, set, tuple, or vector $x$ |
    | $\subset,=,\subseteq$ | the normal proper subset, equality, and subset relations between sets |
    | $\in$ | the membership (is-in) relation between an element and the set it belongs to |
    | $\prec$ | the precedes relation on members of an ordered set: $\sigma_i \prec \sigma_j \textrm{ if and only if } \sigma_i,\sigma_j \in s \textrm{ and } i < j$  where $s$ is an ordered set |
    | \|$X$\| | the size of (the number of elements in) a set $X$ |
    | $\langle X_i \rangle^N_{i=1}$ | a set of $N$ sets $X_i$, indexed by $i$; used in Chapter [\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref" reference="sec:formal_protocol"} in the context of Communicating FSM, taken from    the article on "On Communicating Finite State Machines"[@brand1983communicating] |

!!! info "Logic Symbols"

    | Symbol | Meaning |
    | :--- | :--- |
    | $\implies$ | implies |
    | $\iff$ | if-and-only-if (bi-directional implication) |
    | $\wedge$ | the logical AND operator |
    | $\lnot$ | the logical NOT operator |

!!! info "Directional Messaging Symbols"

    | Symbol | Meaning |
    | :--- | :--- |
    | $\xrightharpoonup{}$ | a message emitted (sent) by a process |
    | $\xleftharpoondown{}$ | $a message received by a process |

!!! info "DFA Symbols"

    | Symbol | Meaning |
    | :--- | :--- |
    | $\xrightarrow{}$ | a transition between states, usually labeled with the transition type (e.g., $\xrightarrow{a}$) |
    | $(\mathcal{Q},q_0,\mathcal{F},\Sigma,\delta)$ | specific symbols for individual DFA components that are introduced when needed in Chapters |
    | $\Big \langle { \langle S_i \rangle }^N_{i=1}, { \langle o_i \rangle }^N_{i=1}, { \langle M_{i,j} \rangle}^N_{i,j=1}, { succ } \Big \rangle$ | formal protocol symbols that are introduced at the beginning of Chapter [\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref" reference="sec:formal_protocol"} |

Our depictions of DFA as figures use common state diagram symbols (circles and arrows).

We follow UML conventions for sequence and class diagrams in Chapters [\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
reference="sec:formal_protocol"} and [\[ch:implementation notes\]](#ch:implementation notes){reference-type="ref" reference="ch:implementation notes"}. We introduce a few additional
notation details specific to Behavior Trees when needed at the beginning of Chapter [\[ch:behavior_trees\]](#ch:behavior_trees){reference-type="ref" reference="ch:behavior_trees"}.
