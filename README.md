# Vultron

[![CI](https://github.com/CERTCC/Vultron/actions/workflows/python-app.yml/badge.svg)](https://github.com/CERTCC/Vultron/actions/workflows/python-app.yml)

Vultron is a research project. It explores how to make a federated, decentralized, and open-source protocol for
coordinated vulnerability disclosure (CVD). Vultron comes from the CERT/CC's decades of experience. The CERT/CC
coordinates the global response to software vulnerabilities.

The goal is to make one protocol for all organizations. An organization can use the protocol to coordinate the
disclosure of vulnerabilities. These vulnerabilities occur in information processing systems, such as software,
hardware, and services. A second goal is to build interoperability across independent organizations. Their processes
and policies are different, but they can work together. Together, they can coordinate an applicable response to
vulnerabilities.

Vultron is a collection of ideas, models, code, and work in progress. It is not ready for production use.

## API entrypoint reference

For uvicorn/ASGI deployment, use `vultron.adapters.driving.fastapi.main:app` as the primary API entrypoint.
The `app_v2` object is in `vultron.adapters.driving.fastapi.app`. This object is the mounted sub-application.
Developers use it directly in local development and tests.

## Background and related work

Vultron is a continuation of the [CERT/CC](https://www.sei.cmu.edu/about/divisions/cert/index.cfm)'s work on improving the coordination of vulnerability disclosure and response.
Our previous work in this area includes:

- The CERT Guide to Coordinated Vulnerability Disclosure
([Version 1.0](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=503330),
[Version 2.0](https://certcc.github.io/CERT-Guide-to-CVD)
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

- A set of high-level processes. These processes show the steps in coordinated vulnerability disclosure.
- A formal protocol. The protocol gives the interactions of those processes.
- A set of behavior logic. Humans can obey this logic as procedures. In many cases, code can also do these actions when
  the state of a case changes. This code needs only minimal human input.
- A minimal data model. The model gives the data that is necessary to monitor each participant's status and the full
  status of the case through the CVD case.

The [Designing Vultron: A Protocol for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=887198)
report first gave all of the items above.

In this repository, we make the first steps to build the protocol and behavior logic from that report.
Currently, the work maps the formal protocol onto the syntax and semantics of the [ActivityPub](https://www.w3.org/TR/activitypub/)
protocol.
You can find examples of these first steps in [doc/examples](doc/examples)

## What is Vultron *not*?

Vultron is **not** a drop-in replacement for these items:

- a *tracking system*, such as [Bugzilla](https://www.bugzilla.org/) or [Jira](https://www.atlassian.com/software/jira)
- a *CVD or threat coordination tool*, such as [VINCE](https://github.com/CERTCC/VINCE) or [MISP](https://www.misp-project.org/)
- a *vulnerability disclosure program*, such as [DC3 VDP](https://www.dc3.mil/Missions/Vulnerability-Disclosure/Vulnerability-Disclosure-Program-VDP/)
- a *vulnerability disclosure platform or service*, such as [HackerOne](https://hackerone.com/), [Bugcrowd](https://www.bugcrowd.com/), or [Synack](https://www.synack.com/)

As an alternative, we hope that Vultron can be a *lingua franca*. It can interchange vulnerability case coordination
data between those systems and services.

Vultron is not a vulnerability prioritization tool. But it is compatible with common prioritization schemes, such as
[SSVC](https://github.com/CERTCC/SSVC) and [CVSS](https://www.first.org/cvss/).

Vultron is not a product. It is a feature set. You can build this feature set into many CVD-related products and
services to let them interoperate.

## Other CERT CVD Resources

For more about our work in modeling, formalizing, and describing the CVD process, see:

- [Designing Vultron: A Protocol for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=887198) (2022) is the initial Vultron report.
  - [SEI Blog post on Vultron](https://insights.sei.cmu.edu/blog/vultron-a-protocol-for-coordinated-vulnerability-disclosure/) (2022-09-26)
  - [SEI Podcast on Vultron](https://youtu.be/8WiSmhxJ2OM) (2023-02-24)
- [CERT Guide to Coordinated Vulnerabilty Disclosure](https://certcc.github.io/CERT-Guide-to-CVD) (2017, 2019)
- [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513) (2021)
  - (abridged as) [Are We Skillful or Just Lucky? Interpreting the Possible Histories of Vulnerability Disclosures](https://dl.acm.org/doi/10.1145/3477431) (2022)
- [Coordinated Vulnerability Disclosure User Stories](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=886543) (2022)
- [Multi-Method Modeling and Analysis of the Cybersecurity Vulnerability Management Ecosystem](https://resources.sei.cmu.edu/asset_files/WhitePaper/2019_019_001_550437.pdf)
(2019) is a snapshot of some related System Dynamics and Agent-based modeling we did of CVD and related processes.
- [Coordinated Vulnerability Disclosure is a Concurrent Process](https://youtu.be/vhA0duqGzmQ) (2015)
is an older talk which looks at a number of prior models of the CVD process, and shows some of our early
attempts to formally describe the concurrency aspects of the CVD process.

## License and Copyright

This repository is licensed under the [MIT (SEI) license](LICENSE.md). See also the included
[copyright statement](COPYRIGHT.md).

Tell us if you have feedback on this topic. This includes feedback if the copyright or license makes it difficult for
you to collaborate with us. Please tell us in an [issue](https://github.com/CERTCC/Vultron/issues/new).
