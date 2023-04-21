# Vultron

Vultron is a research project to explore the creation of a federated, decentralized, and open source protocol for
coordinated vulnerability disclosure (CVD). It has grown out of the CERT/CC's decades of experience in coordinating
global response to software vulnerabilities. The goal is to create a protocol that can be used by any organization
to coordinate the disclosure of vulnerabilities in information processing systems (software, hardware, services, etc.),
and to build a community of interoperability across independent organizations processes and policies that can work 
together to coordinate appropriate responses to vulnerabilities.

Vultron is a collection of ideas, models, code, and work in progress, and is not yet ready for production use.

# Background and related work

Vultron is a continuation of the [CERT/CC](https://kb.cert.org)'s work on improving the coordination of vulnerability disclosure and response.
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
in the ACM Journal _Digital Threats: Research and Practice_.
In 2022, we published a collection of [Coordinated Vulnerability Disclosure User Stories](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=886543)
derived from both our process modeling work and from the experience of building VINCE.
That same year, we published [Designing Vultron: A Protocol for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=887198),
which serves as the basis for the work contained in this repository.

# So what *is* Vultron?

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
report. Currently, the work is focused on mapping the formal protocol onto the syntax and semantics of the [ActivityPub](https://www.w3.org/TR/activitypub/) 
protocol.


# What is Vultron *not*?

Vultron is **not** a drop-in replacement for any particular
- _tracking system_&mdash;e.g., [Bugzilla](https://www.bugzilla.org/), [Jira](https://www.atlassian.com/software/jira)
- _CVD or threat coordination tool_&mdash;e.g., [VINCE](https://github.com/CERTCC/VINCE), [MISP](https://www.misp-project.org/) 
- _Vulnerability disclosure program_&mdash;e.g.,  [DC3 VDP](https://www.dc3.mil/Missions/Vulnerability-Disclosure/Vulnerability-Disclosure-Program-VDP/)
- _Vulnerability disclosure platform or service_&mdash;e.g., [HackerOne](https://hackerone.com/), [Bugcrowd](https://www.bugcrowd.com/), [Synack](https://www.synack.com/)

Instead, it is our hope that Vultron could serve as a _lingua franca_ for the exchange of vulnerability case coordination information
between those systems and services. 

Vultron is not a vulnerability priortization tool, although it is intended to be compatible with common 
prioritization schemes like [SSVC](https://github.com/CERTCC/SSVC) and [CVSS](https://www.first.org/cvss/).

Vultron is not intended to be a product, rather it's meant to be a feature set that can be implemented in a variety of
CVD-related products and services to enable interoperability between them.

