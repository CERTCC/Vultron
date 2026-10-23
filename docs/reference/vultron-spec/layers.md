---
title: "Protocol Specification: Messages and Encoding"
description: >
  Sections 4 and 5 of the Vultron Protocol Specification: the messages a participant sends in each situation of a case, and how they are encoded and transported.
stakeholder_type: [platform-developer]
level: 400
page_type: reference
---

# Messages and Encoding

{% include-markdown "../../includes/normative.md" %}

{% include-markdown "./_full-page-tip.md" %}

This page holds sections 4 and 5 of the [Vultron Protocol Specification](index.md).
§4 says what a participant sends in each situation of a case, and what a message it receives means.
§5 says how a message is encoded on the wire and delivered, including the required Representational State Transfer (REST) transport profile.
The case state messages report the Vendor aware, Fix ready, fix Deployed (VFD) and Public aware, eXploit public, Attacks observed (PXA) dimensions of the Case State (CS).

{% include-markdown "./_messages.md" %}

{% include-markdown "./_encoding-transport.md" %}
