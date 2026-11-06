---
title: "Protocol Specification: Conformance"
description: >
  Section 13 of the Vultron Protocol Specification: capability sets, role taxonomy, role-specific requirements, and the conformance testing approach.
stakeholder_type: [platform-developer]
level: 400
page_type: reference
subject: protocol
---

# Conformance

{% include-markdown "../../includes/normative.md" %}

{% include-markdown "./_full-page-tip.md" %}

This page holds section 13 of the [Vultron Protocol Specification](index.md): what an implementation claims when it claims conformance, and how that claim is tested.
A conforming participant maintains the Report Management (RM), Embargo Management (EM) and Participant Embargo Consent (PEC) state machines, and the Case State (CS) dimensions.
Not every role applies to every participant: only a participant that holds the optional Common Vulnerabilities and Exposures (CVE) Numbering Authority (CNA) role assigns CVE identifiers itself.

{% include-markdown "./_conformance/_intro.md" %}

{% include-markdown "./_conformance/_capability-sets.md" %}

{% include-markdown "./_conformance/_role-taxonomy.md" %}

{% include-markdown "./_conformance/_role-requirements.md" %}

{% include-markdown "./_conformance/_conformance-testing.md" %}
