# Vultron Coordinated Vulnerability Disclosure Protocol

Vultron is a research project to explore the creation of a federated, decentralized,
and open source protocol for coordinated vulnerability disclosure (CVD).
It has grown out of the CERT/CC's decades of experience in coordinating global
response to software vulnerabilities. The goal is to create a protocol that can
be used by any organization to coordinate the disclosure of vulnerabilities in
information processing systems (software, hardware, services, etc.), and to build
a community of interoperability across independent organizations processes and
policies that can work together to coordinate appropriate responses to vulnerabilities.

Vultron is a collection of ideas, models, code, and work in progress, and is not yet ready for production use.

!!! warning "Work in progress"

    We are currently working on the documentation of the Vultron CVD Protocol.
    This documentation is a work in progress and is not yet complete.
    Our focus so far is on the Understanding Vultron section, which describes the protocol in detail.

## How this documentation is organized


!!! tip "Learning About Vultron"

    Tutorials - Learning Oriented
    In the future, we plan to include tutorials to help you learn about Vultron.
    But for now, we recommend that you start with the Understanding Vultron section.
    {== TODO ==}

!!! abstract "Understanding Vultron"

    Explanations - Understanding Oriented

    - [User Stories](user_stories/index.md)
    - [Process Models](process_models/index.md)
    - [Formal Protocol](formal_protocol/index.md)
    - [Behavior Logic](behavior_logic/index.md)
    - [Implementation Notes](implementation_notes/index.md)

!!! question "Using Vultron"

    How-To Guides - Problem Oriented
    In the future, we plan to include how-to guides to help you use Vultron.
    But for now, we recommend that you start with the Understanding Vultron section.
    {== TODO ==}

!!! info "Vultron Reference"

    Reference - Information Oriented
    In the future, we plan to include reference information about Vultron, including code documentation.
    But for now, we recommend that you start with the Understanding Vultron section.
    {== TODO ==}


We are in the process of documenting the Vultron CVD Protocol as we develop a prototype implementation.
We are using the [Diátaxis Framework](https://diataxis.fr/) to organize our documentation into four main categories,
oriented around the different ways that people might need to learn about and use the Vultron protocol.

Our current focus is on the [Understanding Vultron](understanding_vultron.md) section, which describes the protocol
in detail. 

----

Vultron is a continuation of the CERT/CC's work on improving the coordination of vulnerability disclosure and response.
Our previous work in this area includes:
[The CERT Guide to Coordinated Vulnerability Disclosure](https://vuls.cert.org/confluence/display/CVD),
Prioritizing Vulnerability Response: A Stakeholder-Specific Vulnerability Categorization (SSVC) (Version 1.0, Version
2.0, [github](https://github.com/CERTCC/SSVC)), and 
the [Vulnerability Information and Coordination Environment](https://kb.cert.org/vince/) ([VINCE](https://kb.cert.org/vince/) (blog post, github )

A variety of related research, including

- Cybersecurity Information Sharing: Analysing an Email Corpus of Coordinated Vulnerability Disclosure
- Historical Analysis of Exploit Availability Timelines

- More recently, the CERT/CC has been working towards formalizing this knowledge into a protocol for CVD. This work began
with A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure (MPCVD), which also appeared in an
abridged form as Are We Skillful or Just Lucky? Interpreting the Possible Histories of Vulnerability Disclosures in the
ACM Journal Digital Threats: Research and Practice. In 2022, we published a collection of Coordinated Vulnerability
Disclosure User Stories derived from both our process modeling work and from the experience of building VINCE. That same
year, we published Designing Vultron: A Protocol for Multi-Party Coordinated Vulnerability Disclosure (MPCVD), which
serves as the basis for the work contained in this repository.