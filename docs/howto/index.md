# How-to Guides

{% include-markdown "../includes/not_normative.md" %}

This section collects guidance for potential implementations of Vultron.

A complete protocol implementation specification remains a work in progress; a few additional
suggestions for potential implementers follow.

<!-- hr to force spacing -->
<br/>
<br/>
---

!!! tip inline end "Prerequisites"

    The [How-to Guides](index.md) section assumes that you have:
    
    - an interest in implementing the Vultron Protocol
    - basic familiarity with the Vultron Protocol
    - familiarity with the Coordinated Vulnerability Disclosure (CVD) process in general

    If you are unfamiliar with the Vultron Protocol, start with [Explanation](../topics/index.md).
    For technical reference, see [Reference](../reference/index.md).
    If you're just trying to understand the CVD process, start with the [CERT Guide to Coordinated Vulnerability Disclosure](https://certcc.github.io/CERT-Guide-to-CVD){:target="_blank"}.

In this section, you will find:

<div class="grid cards" markdown>

<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml nav or a listed page's description: frontmatter, then run `uv run docs-site --write` -->

<!-- markdownlint-disable MD007 -->
- [Process Implementation](process_implementation.md) — Integrate the Report Management (RM), Embargo Management (EM), and Case State (CS) state machines into an existing workflow management system.
- [Vultron ActivityPub](activitypub/index.md) — Represent Vultron Protocol message types as ActivityPub messages using the ActivityStreams vocabulary.
- [Wiring a Capability](wire_capability.md) — Wire a capability into the reference implementation, replacing a call-out stub with real backend logic.
- **Demo How-Tos**
    - [FVV Demo](demos/fvv-demo.md) — Run the three-actor Finder, Vendor, Vendor (FVV) demo, in which two vendors each advance an independent fix path with no coordinator.
<!-- markdownlint-enable MD007 -->

<!-- END GENERATED SECTION CONTENTS -->

</div>

This section will expand over time to include:

- Basic data model examples
- Behavior logic implementation examples
- Simulation examples
- Communication protocol implementation examples
- Other implementation notes as needed

!!! info "The Vultron Protocol is an interoperability protocol"

    The protocol and data structures outlined in this documentation are intended to facilitate interoperability among individual 
    organizations' workflow management systems.
    As such, they are focused on the exchange of information and data necessary for the Multi-Party CVD (MPCVD) process to function and will 
    not likely be sufficient to fully address any individual organization's vulnerability response process.
