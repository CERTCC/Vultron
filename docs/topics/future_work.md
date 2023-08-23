# Future Work {#ch:future_work}

!!! note "TODO"
    - [ ] regex replace acronym pointers with the acronym
    - [ ] replace first use of an acronym on a page with its expansion (if not already done)
    - [ ] OR replace acronym usage with link to where it's defined
    - [ ] reproduce diagrams using mermaid
    - [ ] replace text about figures to reflect mermaid diagrams
    - [ ] replace latex tables with markdown tables
    - [ ] replace some equations with diagrams (especially for equations describing state changes)
    - [ ] move latex math definitions into note blocks `???+ note _title_` to offset from text
    - [ ] move MUST SHOULD MAY etc statements into note blocks with empty title `!!! note ""` to offset from text
    - [ ] revise cross-references to be links to appropriate files/sections
    - [ ] replace latex citations with markdown citations (not sure how to do this yet)
    - [ ] review text for flow and readability as a web page
    - [ ] add section headings as needed for visual distinction
    - [ ] add links to other sections as needed
    - [ ] add links to external resources as needed
    - [ ] replace phrases like `this report` or `this section` with `this page` or similar
    - [ ] add `above` or `below` for in-page cross-references if appropriate (or just link to the section)
    - [ ] reduce formality of language as needed
    - [ ] move diagrams to separate files and `include-markdown` them

In this chapter, we review a number of items remaining as future work.
We start with a discussion of the need for a [CVD]{acronym-label="CVD"
acronym-form="singular+short"} Directory and some of the difficulties it
might pose. Next, we revisit the concept of churn in the
[RM]{acronym-label="RM" acronym-form="singular+short"} and
[EM]{acronym-label="EM" acronym-form="singular+short"} processes and
elaborate a few ideas to reward efficient behavior. We wrap up the
chapter with some brief thoughts on publication scheduling, the
potential use of ontologies for process interoperability, and ideas for
future modeling and simulation to further improve the
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} process.

## CVD Directory {#sec:cvd_directory}

The idea of [CVD]{acronym-label="CVD" acronym-form="singular+short"}
embargoes implies a means of dividing the world into those who belong in
the embargo and those who do not. Because authentication is not the same
as authorization, we cannot simply rely on knowing *who* a Participant
*is*; we also have to be able to identify *why* they are *relevant* to a
particular case.

Thus, we must ask this question: How do Participants find other relevant
potential Participants to invite to a case? In small
[CVD]{acronym-label="CVD" acronym-form="singular+short"} cases, the
answer might be straightforward: The affected product comes from a known
Vendor, so the only question to answer is how best to contact them. As a
first approximation, Internet search engines offer a de facto baseline
[CVD]{acronym-label="CVD" acronym-form="singular+short"} directory
service simply because they allow any potential Reporter to search for
`<vendor name> vulnerability report` or similar terms to find an
individual Vendor contact.[^1]

But in larger [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} cases, there are a few entangled
problems:

1.  It can be difficult and inefficient to collect contact information
    for all possibly relevant parties.

2.  Even if contact information is widely available using searchable
    resources, many Vendors' preferred contact methods might preclude
    automation of mass notification (or require customized integration
    to ensure interoperability between report senders and receivers).
    Some Vendors only want email. Others require Reporters to create an
    account on their bespoke bug-tracking system before reporting.
    Others ask for submissions via a customized web form. All of these
    examples hinder the interoperability of
    [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
    processes.

3.  It is not always clear which *other* Vendors' products contain the
    affected product, which limits [MPCVD]{acronym-label="MPCVD"
    acronym-form="singular+short"} cases' ability to follow the software
    supply chain.

4.  Sometimes vulnerabilities arise in protocols or specifications where
    multiple implementations are affected. It can be difficult to
    identify Vendors whose products implement specific technologies.
    Software reverse engineering methods can be used to identify
    affected products in some cases.

5.  At the same time, some Vendors treat their product's subcomponents
    as proprietary close-hold information for competitive advantage;
    this might happen, for example, with [OEM]{acronym-label="OEM"
    acronym-form="singular+short"} or white label licensing agreements.
    While it is certainly their prerogative to do so, this desire to
    avoid disclosing internal components of a product can inhibit
    discovery---and therefore disclosure to the Vendor---that a
    vulnerability affects a product.

When it comes to larger scale [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"}, the inefficiency of ad hoc contact
collection via search engines is evident. Creating a directory of
software Vendors and Coordinators and their vulnerability disclosure
programs would be a step in the right direction. Community-operated
directories such as the [FIRST]{acronym-label="FIRST"
acronym-form="singular+short"} member list or Disclose.io serve as
proof-of-concept of the value such systems can provide.[^2] We
especially like the open source model that Disclose.io uses, which
solicits contributions from the community.[^3]

But further improvements to [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} contact management could be made by
standardizing the following:

-   contact information records and the [APIs]{acronym-label="API"
    acronym-form="plural+short"} to access them

-   contact methods, including common protocols such as the one we just
    proposed, in conjunction with common data object models and
    vocabularies or ontologies

-   [SBOM]{acronym-label="SBOM" acronym-form="singular+short"}
    publication and aggregation services

-   mechanisms for Vendors to register their interest in specific
    technologies

The last of these suggested improvements is not without its challenges.
It is difficult to prevent adversarial parties (including Participants
who might be competitors or have motives incompatible with
[CVD]{acronym-label="CVD" acronym-form="singular+short"} principles)
from registering interest in receiving vulnerability reports about
technologies in others' products.

## Reward Functions {#sec:reward_functions}

Further optimization of the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} protocol can be studied with the
development of reward functions to evaluate preferences for certain
[CVD]{acronym-label="CVD" acronym-form="singular+short"} case histories
over others. Householder and Spring{== [@householder2021state] ==} provide a
method to measure skill (${\alpha}_d$) in [CVD]{acronym-label="CVD"
acronym-form="singular+short"} based on a partial order over the
[CVD]{acronym-label="CVD" acronym-form="singular+short"} success
criteria that make up the [CS]{acronym-label="CS"
acronym-form="singular+short"} process, as outlined in
§[\[sec:cvd_success\]](#sec:cvd_success){reference-type="ref"
reference="sec:cvd_success"}. While not yet a fully-realized reward
function, we feel that the ${\alpha}_d$ skill measure has potential as
the basis of a reward function for the [CS]{acronym-label="CS"
acronym-form="singular+short"} model.

The following subsections describe two additional reward functions.

### A Reward Function for Minimizing [RM]{acronym-label="RM" acronym-form="singular+short"} Strings {#sec:rm_reward_function}

In §[\[sec:rm_grammar\]](#sec:rm_grammar){reference-type="ref"
reference="sec:rm_grammar"}, we described a grammar that generates
[RM]{acronym-label="RM" acronym-form="singular+short"} histories. The
state machine can generate arbitrarily long histories because of the
cycles in the state machine graph; however, we found that human
Participants in any real [CVD]{acronym-label="CVD"
acronym-form="singular+short"} case would likely check the amount of
churn. That sort of reliance on human intervention will not scale as
well as a more automatable solution might.

As a result, we suggest that future work might produce a reward function
that can be used to optimize [RM]{acronym-label="RM"
acronym-form="singular+short"} histories. Such a function would need to
include the following:

-   a preference for shorter paths over longer ones

-   a preference for paths that traverse through $q^{rm} \in A$ over
    ones that do not

-   a preference for Vendor attentiveness (The default path for an
    organization with no [CVD]{acronym-label="CVD"
    acronym-form="singular+short"} capability is effectively
    ${q^{em} \in S \xrightarrow{r} R \xrightarrow{i} I \xrightarrow{c}C}$,
    which is short (good!). However, assuming the vulnerability is
    legitimate, half of the desired [CS]{acronym-label="CS"
    acronym-form="singular+short"} criteria can never be achieved
    (bad!). In other words, $\mathbf{F} \prec \mathbf{P}$,
    $\mathbf{F} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{A}$,
    $\mathbf{D} \prec \mathbf{P}$, $\mathbf{D} \prec \mathbf{X}$,
    $\mathbf{D} \prec \mathbf{A}$ are impossible when the Vendor ignores
    the report. No reward function should provide incentive for willful
    Vendor ignorance.)

-   a preference for validation accuracy (Real vulnerabilities should
    pass through $q^{rm} \in V$, while bogus reports should pass through
    $q^{rm} \in I$. The only [RM]{acronym-label="RM"
    acronym-form="singular+short"} paths path not involving at least one
    step through $q^{rm} \in A$ are the following.) $$q^{em} \in
            \begin{cases}
            S \xrightarrow{r} R \xrightarrow{i} I \xrightarrow{c} C & \text{Ignore an invalid case.} \\
            S \xrightarrow{r} R \xrightarrow{v} V \xrightarrow{d} D \xrightarrow{c} C & \text{Defer a valid case.}\\
            S \xrightarrow{r} R \xrightarrow{i} I \xrightarrow{v} V \xrightarrow{d} D \xrightarrow{c} C & \parbox[t]{4cm}{Initially ignore an invalid case, then validate, but defer it anyway.}
            \end{cases}$$ To an outside observer, any of these could be
    interpreted as inattentiveness from an uncommunicative Participant.
    Yet any of these paths might be fine, assuming that (1) the
    Participant communicates about their [RM]{acronym-label="RM"
    acronym-form="singular+short"} state transitions, and (2) the $a$
    transition was possible but intentionally just not taken.

These last two imply some capacity for independent validation of
reports, which, on the surface, seems poised to add cost or complexity
to the process. However, in any [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} case with three or more Participants, a
consensus or voting heuristic could be applied. For example, should a
quorum of Participants agree that a Vendor's products are affected even
if the Vendor denies it, an opportunity exists to capture this
information as part of the case.[^4]

### A Reward Function for Minimizing [EM]{acronym-label="EM" acronym-form="singular+short"} Strings {#sec:em_reward_function}

Similarly, the [EM]{acronym-label="EM" acronym-form="singular+short"}
process also has the potential to generate arbitrarily long histories,
as shown in §[\[sec:em_grammar\]](#sec:em_grammar){reference-type="ref"
reference="sec:em_grammar"}. Again, reliance on humans to resolve this
shortcoming may be acceptable for now; however, looking to the future,
we can imagine a reward function to be optimized. The
[EM]{acronym-label="EM" acronym-form="singular+short"} reward function
might include the following:

-   a preference for short paths

-   a preference for quick agreement (i.e., the $a$ transition appearing
    early in the [EM]{acronym-label="EM" acronym-form="singular+short"}
    history)

-   a limit on how long an [EM]{acronym-label="EM"
    acronym-form="singular+short"} history can get without reaching
    $q^{em} \in A$ at all (i.e., How many proposal-rejection cycles are
    tolerable before giving up?)

## Embargo Management Does Not Deliver Synchronized Publication {#sec:pub_sync}

In our [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
protocol design, we were careful to focus the [EM]{acronym-label="EM"
acronym-form="singular+short"} process on establishing when publication
restrictions are lifted. That is not the same as actually scheduling
publications following the embargo termination. Our experience at the
[CERT/CC]{acronym-label="CERT/CC" acronym-form="singular+short"} shows
that this distinction is rarely a significant problem since many case
Participants simply publish at their own pace shortly after the embargo
ends. However, at times, case Participants may find it necessary to
coordinate even more closely on publication scheduling.

## Ontology {#sec:ontology}

Our proposed [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} protocol does not make its appearance in
uncharted territory, where no existing [CVD]{acronym-label="CVD"
acronym-form="singular+short"} systems or processes exist. Rather, we
propose it as an improvement to interactions among humans, systems, and
business processes that already perform [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} around the world every day. Thus, for
adoption to occur, it will be necessary to map existing systems and
processes into the semantics (and eventually, the syntax) of whatever
protocol emerges as a descendant of our proposal.

Combined with the abstract case class model described in
§[\[sec:case_object\]](#sec:case_object.md){reference-type="ref"
reference="sec:case_object"}, an ontology (e.g., using
[OWL]{acronym-label="OWL" acronym-form="singular+short"}) could
accelerate the semantic interoperability between independent Participant
processes and tools that we set out to improve at the beginning of this
report.

## Modeling and Simulation

The protocol formalisms and Behavior Trees provided in this report
combined with the [CS]{acronym-label="CS" acronym-form="singular+short"}
model described in the Householder and Spring 2021 report
[@householder2021state] point the way toward improvements in
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} modeling
and simulation. Given the complexity of the protocol state interactions
described in Chapter
[\[sec:formal_protocol\]](#sec:formal_protocol/index.md){reference-type="ref"
reference="sec:formal_protocol"} and the corresponding behaviors
described in Chapter
[\[ch:behavior_trees\]](#ch:behavior_trees){reference-type="ref"
reference="ch:behavior_trees"}, we anticipate that modeling and
simulation work will continue progressing toward a reference
implementation of the protocol we describe in this report.

Furthermore, the reward functions outlined in
§[1.2](#sec:reward_functions){reference-type="ref"
reference="sec:reward_functions"} can---once fully realized---be used to
evaluate the efficacy of future modifications to the protocol. This
effort could, in turn, lead to future improvements and optimizations of
the [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
process. The modularity of Behavior Trees provides ready ground for
simulated experiments to determine what additional optimizations to the
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} process
might be made in the future.

[^1]: Vendors can improve their discoverability by using a
    `security.txt` file on their websites. See the security.txt website
    for more information (<https://securitytxt.org/>).

[^2]: For more information, see the FIRST
    (<https://www.first.org/members/teams/>) and Disclose.io
    (<https://disclose.io/programs/>) websites.

[^3]: <https://github.com/disclose/diodb>

[^4]: In fact, this very problem is why the individual Vendor records in
    CERT/CC Vulnerability Notes contain a *CERT/CC Addendum* field.
