---
description: >
  Vultron is an open protocol that lets the systems organizations already use
  for coordinated vulnerability disclosure coordinate a case with each other.
stakeholder_type: ALL
level: 100
---

# The Vultron Coordinated Vulnerability Disclosure Protocol

Vultron is an open protocol for Coordinated Vulnerability Disclosure (CVD): it lets the systems organizations already use coordinate a vulnerability case with each other.
It is a protocol in the way the Simple Mail Transfer Protocol (SMTP) is, not a product in the way a mail service is.
It builds on decades of vulnerability coordination experience at the CERT Coordination Center (CERT/CC).

{% include-markdown "./includes/curr_ver.md" %}

!!! note "Work in progress"

    Vultron is a collection of ideas, models, code, and work in progress, and is **not yet ready for production use**.

## What kind of thing Vultron is

{% include-markdown "./includes/protocol_analogies.md" %}

Email works because a message sent from one provider arrives at any other.
Vultron aims to give vulnerability coordination the same property.

## The problem it solves

Today, coordinating a case across organizations means holding an account on every partner's coordination system.
A vendor that works with three coordinators and a disclosure platform checks four portals, each with its own login, workflow, and idea of the case's state.
Vendors that coordinate directly with each other have no shared system at all.
They fall back to encrypted email and tickets updated by hand, and a person copies every status change from one to the other.

Vultron replaces those per-partner accounts with one protocol.
Your tracker speaks it, your partners' trackers speak it, and the case moves between them as structured messages.
See [What Is Vultron?](topics/background/what-is-vultron.md) for the full answer.

## What Vultron is not

{% include-markdown "./includes/vultron_is_not.md" %}

## Where to start

Pick the description that matches your situation.

<div class="grid cards" markdown>

- :material-shield-search:{ .lg .middle } **You handle vulnerability reports and coordinate cases with other organizations**

    ---

    How a case moves under Vultron, what it asks of each participant, and how it maps onto what you already do.

    [:octicons-arrow-right-24: Start here](start/coordinate-cases.md)

- :fontawesome-solid-code:{ .lg .middle } **You maintain a vulnerability tracker and want it to talk to your partners**

    ---

    What your system sends and when, and where your own logic plugs in.

    [:octicons-arrow-right-24: Start here](start/connect-your-tracker.md)

- :material-chart-timeline-variant:{ .lg .middle } **You study how vulnerability disclosure works and want the models behind it**

    ---

    The process models, the measurements built on them, and the formal protocol definition.

    [:octicons-arrow-right-24: Start here](start/study-the-process.md)

- :material-source-pull:{ .lg .middle } **You want to work on the Vultron reference implementation**

    ---

    Run the demos, then learn how the codebase is built and why.

    [:octicons-arrow-right-24: Start here](start/contribute.md)

</div>

## Who this documentation is for

The site is written for four kinds of reader, and every page declares which of them it addresses.

{% include-markdown "./includes/stakeholder_types.md" %}

## How this documentation is organized

The documentation follows the [Diátaxis Framework](https://diataxis.fr/){:target="_blank"}, which sorts pages into four kinds by what the reader is trying to do.

<div class="grid cards" markdown>

- :material-school:{ .lg .middle } **Tutorials**

    ---

    Step-by-step guided lessons for getting started with Vultron.
    Run the demos and see the protocol in action.

    [:octicons-arrow-right-24: Tutorials](tutorials/index.md)

- :fontawesome-solid-book-open:{ .lg .middle } **Explanation**

    ---

    Background, concepts, process models, and behavior logic.
    Builds understanding of how and why Vultron works.

    [:octicons-arrow-right-24: Explanation](topics/index.md)

- :fontawesome-solid-wrench:{ .lg .middle } **How-to Guides**

    ---

    Goal-oriented guidance for implementers.
    ActivityPub integration, wiring capabilities, and protocol implementation advice.

    [:octicons-arrow-right-24: How-to Guides](howto/index.md)

- :material-bookshelf:{ .lg .middle } **Reference**

    ---

    The protocol specification, message types, the formal protocol, and International Organization for Standardization (ISO) crosswalks.

    [:octicons-arrow-right-24: Reference](reference/index.md)

</div>

Research material sits outside those four, in its own [Research](research/index.md) section: measuring CVD across many cases, and other uses of the case state model.
The project's decision records, requirements, and generated code references are reached from [Working on This Implementation](about/project_record.md).

## Background

The Vultron Protocol is a continuation of the CERT/CC's work on improving the coordination of vulnerability disclosure and response.
Our previous work in this area includes:

- [The CERT Guide to Coordinated Vulnerability Disclosure](https://certcc.github.io/CERT-Guide-to-CVD){:target="_blank"}
- Prioritizing Vulnerability Response: A Stakeholder-Specific Vulnerability Categorization (SSVC) ([Version 1.0](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=636379){:target="_blank"}, [Version 2.0](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=653459){:target="_blank"}, [GitHub](https://github.com/CERTCC/SSVC){:target="_blank"})
- The [Vulnerability Information and Coordination Environment](https://kb.cert.org/vince/){:target="_blank"}
  ([VINCE](https://kb.cert.org/vince/){:target="_blank"})
  ([blog post](https://insights.sei.cmu.edu/news/certcc-releases-vince-software-vulnerability-collaboration-platform/){:target="_blank"},
  [GitHub](https://github.com/CERTCC/VINCE){:target="_blank"})

along with a variety of related research, including

- [Cybersecurity Information Sharing: Analysing an Email Corpus of Coordinated Vulnerability Disclosure](https://weis2021.econinfosec.org/wp-content/uploads/sites/9/2021/06/weis21-sridhar.pdf){:target="_blank"} (WEIS 2021)
- [Historical Analysis of Exploit Availability Timelines](https://www.usenix.org/conference/cset20/presentation/householder){:target="_blank"} (CSET 2020)

More recently, the CERT/CC has been working towards formalizing this knowledge into a protocol for CVD.
Our recent work in this area includes:

- [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513){:target="_blank"} (MPCVD), which also appeared in an abridged form as [Are We Skillful or Just Lucky? Interpreting the Possible Histories of Vulnerability Disclosures](https://doi.org/10.1145/3477431){:target="_blank"} in the Association for Computing Machinery (ACM) journal Digital Threats: Research and Practice
- A collection of [Coordinated Vulnerability Disclosure User Stories](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=886543){:target="_blank"} derived from both our process modeling work and from the experience of building VINCE.
  These user stories are collected in the [User Stories](reference/user_stories/index.md) section of this documentation.
- [Designing Vultron: A Protocol for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=887198){:target="_blank"} (MPCVD),
  which serves as the basis for the work contained here.
