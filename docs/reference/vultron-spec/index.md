---
title: Vultron Protocol Specification
description: >
  The Vultron Protocol specification: its messages, their encoding and
  transport, and the state machines participants use to track a shared case.
stakeholder_type: [platform-developer]
level: 400
page_type: routing
subject: protocol
contents: routing
---

# Vultron Protocol Specification

{% include-markdown "./_full-page-tip.md" %}

{% include-markdown "./_abstract.md" %}

## Parts

The specification is published one part per page.
The parts are listed in reading order, and each page holds the sections listed beside it, from the introduction to the Internet Assigned Numbers Authority (IANA) and security considerations.

- [Introduction and Overview](introduction.md): §1 Introduction, §2 Terminology, and §3 Protocol Overview.
- [Messages and Encoding](layers.md): §4 Messages and §5 Encoding and Transport.
- [Case Tracking Models](tracking-models.md): §6 Report Management (RM) State Machine, §7 Embargo Management (EM) State Machine, §8 Case State (CS) Dimensions, and §9 Participant Embargo Consent (PEC) State Machine.
- [Coordination, Interactions, and Lifecycle](interactions.md): §10 Case Coordination, §11 Model Interactions and Cascade Rules, and §12 Participant Lifecycle Within a Case.
- [Conformance](conformance.md): §13 Conformance.
- [Requirements Catalog](requirements/index.md): §14 Requirements Catalog, which lists every `protocol` and `foundation` requirement once.
- [Considerations and References](considerations.md): §15 IANA and Namespace Considerations, §16 Security Considerations, and §17 References.

The Requirements Catalog is published one theme per page:

- §14.1 [Vultron Protocol](requirements/vultron-protocol.md)
- §14.2 [Messages and Vocabulary](requirements/messages.md)
- §14.3 [Report, Embargo and Case State Behavior](requirements/state-behavior.md)
- §14.4 [Case Management](requirements/case-management.md)
- §14.5 [Case Ledger and Replication](requirements/ledger-replication.md)
- §14.6 [Message Processing](requirements/message-processing.md)
- §14.7 [Transport and Security](requirements/transport-security.md)
- §14.8 [Inherited Requirements](requirements/foundation.md)

## Annexes

The annexes illustrate and explain the protocol, and nothing in them is normative.

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

{% include-markdown "../../start/_paths/connect-your-tracker/reference__vultron-spec__index.md" %}
