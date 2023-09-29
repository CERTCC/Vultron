# The Vultron Coordinated Vulnerability Disclosure Protocol

!!! warning inline end "Work in progress"

    We are currently working on the documentation of the Vultron CVD Protocol.
    This documentation is a work in progress and is not yet complete.
    Our focus so far is on
    
    - [Understanding Vultron](topics/background/index.md), which describes the protocol in detail
    - [Implementing Vultron](howto/index.md), which provides guidance for potential implementations of Vultron
    - [Reference](reference/formal_protocol/index.md), which provides the formal protocol specification

The Vultron Protocol is a research project to explore the creation of a federated, decentralized, and open source protocol for 
coordinated vulnerability disclosure (CVD).
It has grown out of the CERT/CC's decades of experience in coordinating global response to software vulnerabilities.
Our goal is to create a protocol that can be used by any organization to coordinate the disclosure of vulnerabilities in
information processing systems (software, hardware, services, etc.), and to build a community of interoperability across
independent organizations, processes, and policies that can work together to coordinate appropriate responses to vulnerabilities.

The Vultron Protocol is a collection of ideas, models, code, and work in progress, and is not yet ready for production use.

{% include-markdown "./includes/curr_ver.md" %}

## How this documentation is organized


!!! tip inline "Learning About Vultron"

    The [Learning Vultron](tutorials/index.md) section is intended to eventually include tutorials and other 
    information about the Vultron Protocol that is oriented towards novice users and getting started with the protocol.
    However, because we are still in the early stages of the project, this section is just a placeholder for now.

!!! abstract inline end "Understanding Vultron"

    The [Understanding Vultron](topics/background/index.md) section includes background information about Vultron,
    including the motivation for the project, the problem space that we are trying to address, and the design principles
    that we are using to guide our work. It also includes a detailed description of the Vultron Protocol, including
    the state machines and behavior logic that we use to model the behavior of the protocol.

!!! question inline  "Implementing Vultron"

    The [Implementing Vultron](howto/index.md) section includes guidance for potential implementations of Vultron.
    In the future, we plan to include how-to guides to help you use Vultron, but for now it is focused on guidance for
    potential implementers of Vultron.

!!! info inline end "Vultron Protocol Reference"

    The [Reference](reference/index.md) section includes the formal Vultron Protocol specification, crosswalks the 
    protocol with other related standards and protocols, etc.
    In the future, we plan to include other reference information about Vultron, including code documentation.

We are in the process of documenting the Vultron CVD Protocol as we work towards a prototype implementation.
We are using the [Diátaxis Framework](https://diataxis.fr/) to organize our documentation into four main categories,
oriented around the different ways that people might need to learn about and use the Vultron Protocol.

Our current focus is on the [Understanding Vultron](topics/background/index.md) section, which describes the protocol
in detail. 


## Background

The Vultron Protocol is a continuation of the CERT/CC's work on improving the coordination of vulnerability disclosure and response.
Our previous work in this area includes:

- [The CERT Guide to Coordinated Vulnerability Disclosure](https://vuls.cert.org/confluence/display/CVD)
- Prioritizing Vulnerability Response: A Stakeholder-Specific Vulnerability Categorization (SSVC) ([Version 1.0](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=636379), [Version
2.0](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=653459), [github](https://github.com/CERTCC/SSVC))
- The [Vulnerability Information and Coordination Environment](https://kb.cert.org/vince/)
  ([VINCE](https://kb.cert.org/vince/))
  ([blog post](https://insights.sei.cmu.edu/news/certcc-releases-vince-software-vulnerability-collaboration-platform/),
  [github](https://github.com/CERTCC/VINCE))

along with a variety of related research, including

- [Cybersecurity Information Sharing: Analysing an Email Corpus of Coordinated Vulnerability Disclosure](https://weis2021.econinfosec.org/wp-content/uploads/sites/9/2021/06/weis21-sridhar.pdf) (WEIS 2021)
- [Historical Analysis of Exploit Availability Timelines](https://www.usenix.org/conference/cset20/presentation/householder) (CSET 2020)

More recently, the CERT/CC has been working towards formalizing this knowledge into a protocol for CVD.
Our recent work in this area includes:

- [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513) (MPCVD), which also appeared in an
abridged form as [Are We Skillful or Just Lucky? Interpreting the Possible Histories of Vulnerability Disclosures](https://doi.org/10.1145/3477431) in the
ACM Journal Digital Threats: Research and Practice 
- A collection of [Coordinated Vulnerability Disclosure User Stories](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=886543) derived from both our process modeling work and from the experience of building VINCE.
  These user stories are collected in the [User Stories](topics/user_stories/index.md) section of this documentation. 
- [Designing Vultron: A Protocol for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=887198) (MPCVD),
  which serves as the basis for the work contained here.