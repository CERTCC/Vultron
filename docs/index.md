# The Vultron Coordinated Vulnerability Disclosure Protocol

The Vultron Protocol is a research project to develop a federated, decentralized,
and open-source protocol for coordinated vulnerability disclosure (CVD).
Built on CERT/CC's decades of experience coordinating global software vulnerability
response, Vultron aims to serve as a *lingua franca* for sharing CVD case
coordination data across independent organizations, tools, and policies.
It targets security researchers, vulnerability coordinators, tool builders, and
anyone seeking interoperability in the CVD ecosystem.

!!! note "Work in progress"

    Vultron is a collection of ideas, models, code, and work in progress, and is
    **not yet ready for production use**.
    We are currently working on the documentation of the Vultron CVD Protocol.
    Our focus so far is on

    - [Explanation](topics/index.md), which describes the
      protocol in detail
    - [How-to Guides](howto/index.md), which provides guidance for
      potential implementations of Vultron
    - [Reference](reference/formal_protocol/index.md), which provides the formal
      protocol specification

{% include-markdown "./includes/curr_ver.md" %}

## So what *is* Vultron?

Vultron is:

- A set of high-level processes representing the steps involved in coordinated
  vulnerability disclosure
- A formal protocol describing the interactions of those processes
- A set of behavior logic that can be implemented as either procedures for humans
  to follow or (in many cases) code that can perform actions in response to state
  changes in a case with minimal human input
- A minimal data model for what information is necessary to track participant
  status and the overall case status through the course of handling a CVD case

The above were all initially described in the
[Designing Vultron: A Protocol for Multi-Party Coordinated Vulnerability Disclosure
(MPCVD)](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=887198){:target="_blank"}
report.
In this repository, we are taking the first steps towards implementing the protocol
and behavior logic described in that report.
The current work focuses on mapping the formal protocol onto the syntax and
semantics of the [ActivityPub](https://www.w3.org/TR/activitypub/){:target="_blank"}
protocol.

## What is Vultron *not*?

Vultron is **not** a drop-in replacement for any particular

- *tracking system*&mdash;e.g.,
  [Bugzilla](https://www.bugzilla.org/){:target="_blank"},
  [Jira](https://www.atlassian.com/software/jira){:target="_blank"}
- *CVD or threat coordination tool*&mdash;e.g.,
  [VINCE](https://github.com/CERTCC/VINCE){:target="_blank"},
  [MISP](https://www.misp-project.org/){:target="_blank"}
- *Vulnerability disclosure program*&mdash;e.g.,
  [DC3 VDP](https://www.dc3.mil/Missions/Vulnerability-Disclosure/Vulnerability-Disclosure-Program-VDP/){:target="_blank"}
- *Vulnerability disclosure platform or service*&mdash;e.g.,
  [HackerOne](https://hackerone.com/){:target="_blank"},
  [Bugcrowd](https://www.bugcrowd.com/){:target="_blank"},
  [Synack](https://www.synack.com/){:target="_blank"}

Instead, it is our hope that Vultron could serve as a *lingua franca* for the
exchange of vulnerability case coordination information between those systems and
services.

Vultron is not a vulnerability prioritization tool, although it is intended to be
compatible with common prioritization schemes like
[SSVC](https://github.com/CERTCC/SSVC){:target="_blank"} and
[CVSS](https://www.first.org/cvss/){:target="_blank"}.

Vultron is not intended to be a product; rather, it is meant to be a feature set
that can be implemented in a variety of CVD-related products and services to enable
interoperability between them.

## How this documentation is organized

We are in the process of documenting the Vultron CVD Protocol as we work towards
a prototype implementation.
We are using the [Diátaxis Framework](https://diataxis.fr/){:target="_blank"} to
organize our documentation into four main categories, oriented around the different
ways that people might need to learn about and use the Vultron Protocol.

Our current focus is on the [Explanation](topics/index.md)
section, which describes the protocol in detail.

<div class="grid cards" markdown>

- :material-school:{ .lg .middle } **Tutorials**

    ---

    Step-by-step guided lessons for getting started with Vultron. Run the
    demos and see the protocol in action.

    [:octicons-arrow-right-24: Tutorials](tutorials/index.md)

- :fontawesome-solid-book-open:{ .lg .middle } **Explanation**

    ---

    Background, concepts, process models, and formal protocol description.
    Builds understanding of how and why Vultron works.

    [:octicons-arrow-right-24: Explanation](topics/index.md)

- :fontawesome-solid-wrench:{ .lg .middle } **How-to Guides**

    ---

    Goal-oriented guidance for implementers. Data models, ActivityPub
    integration, and protocol implementation advice.

    [:octicons-arrow-right-24: How-to Guides](howto/index.md)

- :material-bookshelf:{ .lg .middle } **Reference**

    ---

    Formal protocol specification, case state listings, code documentation,
    ontologies, and ISO crosswalks.

    [:octicons-arrow-right-24: Reference](reference/index.md)

</div>

## Who is this documentation for?

<div class="grid cards" markdown>

- :material-shield-search:{ .lg .middle } **CVD Practitioner**

    ---

    You coordinate vulnerability disclosures, work at a CERT/CSIRT, or manage
    vulnerability response for your organization. You want to understand how
    Vultron models the CVD process and whether it fits your workflow.

    [:octicons-arrow-right-24: Start with Explanation](topics/index.md)

- :fontawesome-solid-code:{ .lg .middle } **Software Developer**

    ---

    You are building a vulnerability tracking system, CVD tool, or
    interoperability layer and want to implement the Vultron Protocol.

    [:octicons-arrow-right-24: Start with How-to Guides](howto/index.md)

- :material-source-pull:{ .lg .middle } **Vultron Contributor**

    ---

    You are working on the Vultron reference implementation and want to
    understand the codebase, run the demos, or contribute to the project.

    [:octicons-arrow-right-24: Start with Tutorials](tutorials/index.md)

</div>

## Background

The Vultron Protocol is a continuation of the CERT/CC's work on improving the coordination of vulnerability disclosure and response.
Our previous work in this area includes:

- [The CERT Guide to Coordinated Vulnerability Disclosure](https://certcc.github.io/CERT-Guide-to-CVD){:target="_blank"}
- Prioritizing Vulnerability Response: A Stakeholder-Specific Vulnerability Categorization (SSVC) ([Version 1.0](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=636379){:target="_blank"}, [Version
2.0](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=653459){:target="_blank"}, [github](https://github.com/CERTCC/SSVC){:target="_blank"})
- The [Vulnerability Information and Coordination Environment](https://kb.cert.org/vince/){:target="_blank"}
  ([VINCE](https://kb.cert.org/vince/){:target="_blank"})
  ([blog post](https://insights.sei.cmu.edu/news/certcc-releases-vince-software-vulnerability-collaboration-platform/){:target="_blank"},
  [github](https://github.com/CERTCC/VINCE){:target="_blank"})

along with a variety of related research, including

- [Cybersecurity Information Sharing: Analysing an Email Corpus of Coordinated Vulnerability Disclosure](https://weis2021.econinfosec.org/wp-content/uploads/sites/9/2021/06/weis21-sridhar.pdf){:target="_blank"} (WEIS 2021)
- [Historical Analysis of Exploit Availability Timelines](https://www.usenix.org/conference/cset20/presentation/householder){:target="_blank"} (CSET 2020)

More recently, the CERT/CC has been working towards formalizing this knowledge into a protocol for CVD.
Our recent work in this area includes:

- [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513){:target="_blank"} (MPCVD), which also appeared in an
abridged form as [Are We Skillful or Just Lucky? Interpreting the Possible Histories of Vulnerability Disclosures](https://doi.org/10.1145/3477431){:target="_blank"} in the
ACM Journal Digital Threats: Research and Practice
- A collection of [Coordinated Vulnerability Disclosure User Stories](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=886543){:target="_blank"} derived from both our process modeling work and from the experience of building VINCE.
  These user stories are collected in the [User Stories](reference/user_stories/index.md) section of this documentation.
- [Designing Vultron: A Protocol for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=887198){:target="_blank"} (MPCVD),
  which serves as the basis for the work contained here.
