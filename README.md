# Vultron

Vultron is a research project to explore the creation of a federated, decentralized, and open source protocol for
coordinated vulnerability disclosure (CVD). It has grown out of the CERT/CC's decades of experience in coordinating
global response to software vulnerabilities. The goal is to create a protocol that can be used by any organization
to coordinate the disclosure of vulnerabilities in information processing systems (software, hardware, services, etc.),
and to build a community of interoperability across independent organizations processes and policies that can work
together to coordinate appropriate responses to vulnerabilities.

Vultron is a collection of ideas, models, code, and work in progress, and is not yet ready for production use.

## Background and related work

Vultron is a continuation of the [CERT/CC](https://www.sei.cmu.edu/about/divisions/cert/index.cfm)'s work on improving the coordination of vulnerability disclosure and response.
Our previous work in this area includes:

- The CERT Guide to Coordinated Vulnerability Disclosure
([Version 1.0](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=503330),
[Version 2.0](https://vuls.cert.org/confluence/display/CVD)
)
- Prioritizing Vulnerability Response: A Stakeholder-Specific Vulnerability Categorization (SSVC)
([Version 1.0](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=636379),
[Version 2.0](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=653459),
[github](https://github.com/CERTCC/SSVC)
)
- The Vulnerability Information and Coordination Environment (VINCE)
([blog post](https://insights.sei.cmu.edu/news/certcc-releases-vince-software-vulnerability-collaboration-platform/),
[github](https://github.com/CERTCC/VINCE)
)

- A variety of related research, including
  - [Cybersecurity Information Sharing: Analysing an Email Corpus of Coordinated Vulnerability Disclosure](https://www.research.ed.ac.uk/en/publications/cybersecurity-information-sharing-analysing-an-email-corpus-of-co)
  - [Historical Analysis of Exploit Availability Timelines](https://www.usenix.org/conference/cset20/presentation/householder)

More recently, the CERT/CC has been working towards formalizing this knowledge into a protocol for CVD.
This work began
with [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513),
which also appeared in an abridged form as [Are We Skillful or Just Lucky? Interpreting the Possible Histories of Vulnerability Disclosures](https://dl.acm.org/doi/10.1145/3477431)
in the ACM Journal *Digital Threats: Research and Practice*.
In 2022, we published a collection of [Coordinated Vulnerability Disclosure User Stories](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=886543)
derived from both our process modeling work and from the experience of building VINCE.
That same year, we published [Designing Vultron: A Protocol for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=887198),
which serves as the basis for the work contained in this repository.

## So what *is* Vultron?

Vultron is:

- A set of high-level processes representing the steps involved in coordinated vulnerability disclosure
- A formal protocol describing the interactions of those processes
- A set of behavior logic that can be implemented as either procedures for humans to follow or (in many cases) code that
  can perform actions in response to state changes in a case with minimal human input
- A minimal data model for what information is necessary to track participant status and the overall case status through
  the course of handling a CVD case

The above were all initially described in the
[Designing Vultron: A Protocol for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=887198) report.

In this repository, we are taking the first steps towards implementing the protocol and behavior logic described in that
report.
Currently, the work is focused on mapping the formal protocol onto the syntax and semantics of the [ActivityPub](https://www.w3.org/TR/activitypub/)
protocol.
Examples of our first steps in that direction can be found in [doc/examples](doc/examples)

## What is Vultron *not*?

Vultron is **not** a drop-in replacement for any particular

- *tracking system*&mdash;e.g., [Bugzilla](https://www.bugzilla.org/), [Jira](https://www.atlassian.com/software/jira)
- *CVD or threat coordination tool*&mdash;e.g., [VINCE](https://github.com/CERTCC/VINCE), [MISP](https://www.misp-project.org/)
- *Vulnerability disclosure program*&mdash;e.g.,  [DC3 VDP](https://www.dc3.mil/Missions/Vulnerability-Disclosure/Vulnerability-Disclosure-Program-VDP/)
- *Vulnerability disclosure platform or service*&mdash;e.g., [HackerOne](https://hackerone.com/), [Bugcrowd](https://www.bugcrowd.com/), [Synack](https://www.synack.com/)

Instead, it is our hope that Vultron could serve as a *lingua franca* for the exchange of vulnerability case coordination information
between those systems and services.

Vultron is not a vulnerability priortization tool, although it is intended to be compatible with common
prioritization schemes like [SSVC](https://github.com/CERTCC/SSVC) and [CVSS](https://www.first.org/cvss/).

Vultron is not intended to be a product, rather it's meant to be a feature set that can be implemented in a variety of
CVD-related products and services to enable interoperability between them.

## Other CERT CVD Resources

For more about our work in modeling, formalizing, and describing the CVD process, see:

- [Designing Vultron: A Protocol for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=887198) (2022) is the initial Vultron report.
  - [SEI Blog post on Vultron](https://insights.sei.cmu.edu/blog/vultron-a-protocol-for-coordinated-vulnerability-disclosure/) (2022-09-26)
  - [SEI Podcast on Vultron](https://youtu.be/8WiSmhxJ2OM) (2023-02-24)
- [CERT Guide to Coordinated Vulnerabilty Disclosure](https://vuls.cert.org/confluence/display/CVD) (2017, 2019)
- [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513) (2021)
  - (abridged as) [Are We Skillful or Just Lucky? Interpreting the Possible Histories of Vulnerability Disclosures](https://dl.acm.org/doi/10.1145/3477431) (2022)
- [Coordinated Vulnerability Disclosure User Stories](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=886543) (2022)
- [Multi-Method Modeling and Analysis of the Cybersecurity Vulnerability Management Ecosystem](https://resources.sei.cmu.edu/asset_files/WhitePaper/2019_019_001_550437.pdf)
(2019) is a snapshot of some related System Dynamics and Agent-based modeling we did of CVD and related processes.
- [Coordinated Vulnerability Disclosure is a Concurrent Process](https://youtu.be/vhA0duqGzmQ) (2015)
is an older talk which looks at a number of prior models of the CVD process, and shows some of our early
attempts to formally describe the concurrency aspects of the CVD process.

## License and Copyright

We are still working out the correct licensing model for this effort, but for now, this repository is covered by the
included [copyright statement](COPYRIGHT.md).

If you have feedback on this topic (including whether the copyright/license is causing difficulty for you to collaborate
with us on this project), please let us know in an [issue](https://github.com/CERTCC/Vultron/issues/new).
