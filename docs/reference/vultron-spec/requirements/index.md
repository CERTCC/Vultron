---
title: "Protocol Specification: Requirements Catalog"
description: >
  Section 14 of the Vultron Protocol Specification: every protocol and foundation requirement, once, grouped by theme.
stakeholder_type: [platform-developer]
level: 400
page_type: routing
subject: protocol
contents: routing
---

# Requirements Catalog

{% include-markdown "../../../includes/normative.md" %}

{% include-markdown "../_full-page-tip.md" %}

This page opens section 14 of the [Vultron Protocol Specification](../index.md).

{% include-markdown "../_catalog/_intro.md" %}

The catalog is published one theme per page:

- §14.1 [Vultron Protocol](vultron-protocol.md): the core protocol and its Report Management (RM), Embargo Management (EM) and Case State (CS) models.
- §14.2 [Messages and Vocabulary](messages.md): how messages map onto AS2 activities, the vocabulary, and message validation.
- §14.3 [Report, Embargo and Case State Behavior](state-behavior.md): the state machines and how a participant behaves in each state.
- §14.4 [Case Management](case-management.md): cases, case proposals, participant roles, and asks.
- §14.5 [Case Ledger and Replication](ledger-replication.md): the case ledger, its synchronization, and participant case replicas.
- §14.6 [Message Processing](message-processing.md): how a receiver handles a message, and which sender is entitled to change which status.
- §14.7 [Transport and Security](transport-security.md): the HTTP transport, inbox, outbox, signing, and encryption.
- §14.8 [Inherited Requirements](foundation.md): the `foundation` tier, inherited from AS2, ActivityPub, and HTTP.
