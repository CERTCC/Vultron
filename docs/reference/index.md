---
stakeholder_type: ALL
level: 200
---

# Vultron Protocol Reference

!!! tip inline end "Prerequisites"

    The [Reference](index.md) section assumes that you have

    - specific questions about or a desire for a detailed understanding of the Vultron Protocol
    - familiarity with the [Explanation](../topics/index.md) section
    - familiarity with the Coordinated Vulnerability Disclosure (CVD) process in general
     
    If you are unfamiliar with the Vultron Protocol, start with [Explanation](../topics/index.md).
    If you are familiar enough with the Vultron Protocol that you're interested in implementing it, see [How-to Guides](../howto/index.md).
    And finally, if you're just trying to understand the CVD process, start with the [CERT Guide to Coordinated Vulnerability Disclosure](https://certcc.github.io/CERT-Guide-to-CVD){:target="_blank"}.

The Vultron Protocol Reference includes the formal Vultron Protocol specification, and crosswalks the
protocol with other related standards and protocols, including:

<div class="grid cards" markdown>

<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml nav or a listed page's description: frontmatter, then run `uv run docs-site --write` -->

<!-- markdownlint-disable MD007 -->
- [Terms and Definitions](terms.md) — The Coordinated Vulnerability Disclosure (CVD) stakeholder roles and case terms used throughout this documentation.
- [Versioning](versioning.md) — The version-numbering scheme for the Vultron Protocol.
- [ISO Crosswalk](iso_crosswalks/index.md) — A crosswalk of the Vultron Protocol against the ISO/IEC standards on vulnerability handling and disclosure.
- [User Stories](user_stories/index.md) — Requirements captured as user stories.
- **Protocol Architecture**
    - [Concept Taxonomy](vultron-taxonomy.md) — Reference definitions for the distinct concepts that together constitute Vultron. Use this document to understand what each named concept covers, what it excludes, and how the concepts relate to each other.
    - [Glossary](glossary.md) — Domain terminology for the Vultron Coordinated Vulnerability Disclosure (CVD) protocol and its reference implementation, with the aliases to avoid.
    - [Protocol Specification](vultron-spec/index.md) — The Vultron Protocol specification: its semantic and syntactic layers and the state machines participants use to track a shared case.
- [Notation](notation.md) — Notation conventions used throughout the documentation.
- **ActivityPub**
    - [Vultron AS Objects](activitypub/objects.md) — The Vultron ActivityStreams objects that extend the ActivityStreams vocabulary.
- [FV Demo Protocol](fv-demo-protocol.md) — The message-level protocol interactions of the Finder + Vendor (FV) demo, for developers building interoperable actors.
- [Trigger API](trigger-api.md) — The `POST /actors/{actor_id}/trigger/{behavior}` endpoints, each of which starts a protocol behavior on an actor's behalf.
- [Protocol Quick Reference](quick_reference.md) — A single-page summary of the protocol's state machines, message types, and how they interact.
- [Formal Protocol](formal_protocol/index.md) — The Multi-Party Coordinated Vulnerability Disclosure (MPCVD) process defined as a communicating hierarchical state machine.
- [Messages](messages/index.md) — How the formal message set relates to the ActivityStreams 2.0 (AS2) wire vocabulary the prototype sends and receives.
- [Specifications](specs/index.md) — Structured requirements organized by portability tier: Protocol, Architecture, Project, and Process.
- [SSVC Crosswalk](ssvc_crosswalk.md) — A crosswalk of the Vultron Protocol against Stakeholder-Specific Vulnerability Categorization (SSVC).
<!-- markdownlint-enable MD007 -->

<!-- END GENERATED SECTION CONTENTS -->

</div>

Metrics and benchmarks for Coordinated Vulnerability Disclosure (CVD) efficacy are explained in [Measuring CVD](../topics/measuring_cvd/index.md).
