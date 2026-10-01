---
title: Vultron Protocol Specification
description: >
  The Vultron Protocol specification: its semantic and syntactic
  layers and the state machines participants use to track a shared case.
stakeholder_type: [platform-developer]
level: 400
contents: routing
---

# Vultron Protocol Specification

{% include-markdown "./_full-page-tip.md" %}

{% include-markdown "./_abstract.md" %}

## Parts

The specification is published one part per page.
The parts are numbered in reading order, and each page holds the sections listed beside it, from the introduction to the Internet Assigned Numbers Authority (IANA) and security considerations.

- [Introduction and Overview](introduction.md): §1 Introduction, §2 Terminology, and §3 Protocol Overview.
- [Protocol Layers](layers.md): §4 Semantic Layer — Message Meanings and §5 Syntactic Layer — Wire Format.
- [Case Tracking Models](tracking-models.md): §6 Report Management (RM) State Machine, §7 Embargo Management (EM) State Machine, §8 Case State (CS) Dimensions, and §9 Participant Embargo Consent (PEC) State Machine.
- [Interactions and Lifecycle](interactions.md): §10 Model Interactions and Cascade Rules and §11 Participant Lifecycle Within a Case.
- [Conformance](conformance.md): §12 Conformance.
- [Considerations and References](considerations.md): §13 IANA and Namespace Considerations, §14 Security Considerations, and §15 References.

{% include-markdown "./_annexes.md" %}

Annexes A and B trace Coordinated Vulnerability Disclosure (CVD) cases from first contact to closure.

Annexes A and B trace Coordinated Vulnerability Disclosure (CVD) cases from first contact to closure.

- [Annex A Worked Example: Single-Vendor CVD](annex-a-single-vendor.md)
- [Annex B Worked Example: Multi-Party CVD](annex-b-multi-party.md)
- [Annex C Notation Reference](annex-c-notation.md)
- [Annex D Possible Case Histories](annex-d-case-histories.md)
- [Annex E Relationship to ActivityPub](annex-e-activitypub.md)
- [Annex F Behavior Trees as an Implementation Pattern](annex-f-behavior-trees.md)
- [Annex G Capability Shapes](annex-g-capability-shapes.md)

## Open Questions and the Single-Page Edition

[Open Questions](open-questions.md) collects the questions this version of the specification leaves unresolved.
[The single-page edition](full.md) holds every section and annex in order, for printing or for searching the whole text at once.
