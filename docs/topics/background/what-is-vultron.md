# What Is Vultron?

!!! tip inline end "Is this page for me?"

    This page is written for two readers:

    - A **CVD practitioner** (security researcher, coordinator, CERT/CSIRT
      analyst) who wants to know whether Vultron solves a problem they
      actually have.
    - A **systems architect** who wants to understand what "Vultron
      conformance" would mean for their organization's tools and processes.

    If you are already sold and want to implement, jump to
    [How-to Guides](../../howto/index.md).

CVD is a multi-party coordination problem. When a vulnerability spans several
vendors, a coordinator, and a national CERT, the parties typically coordinate
via email threads, shared spreadsheets, and bespoke one-off integrations.
Every new coordination relationship requires custom effort, and there is no
shared protocol: a system built for one organization's CVD workflow cannot
interoperate with another's without explicit bilateral agreements.

Vultron is a proposal for changing that. It is a federated, open-source
protocol for CVD coordination — one that any tool, CERT, or vendor can
implement to participate in ad-hoc coordination across organizational
boundaries.

## Vultron as a Protocol in Four Senses

The word *protocol* is doing a lot of work here. Vultron is a protocol in
four distinct senses, and understanding all four is the fastest way to see
what it can and cannot do for you.

### 1. Technical — Message Format and Syntax

Vultron specifies a wire format based on
[ActivityStreams 2.0](https://www.w3.org/TR/activitystreams-core/){:target="_blank"}
for the messages that CVD participants exchange: report submissions, state
change notifications, embargo proposals, and invitations. Any system can
implement this wire format independently of the others.

This is the *syntactic* layer: two systems speaking Vultron at this level can
exchange structured data, even if they do not yet interpret it identically.

### 2. Procedural — Behavior Logic

Beyond the wire format, Vultron specifies *behavioral requirements*: given a
current case state and a received message, what should a well-behaved
participant do next? These requirements are captured as machine-readable specs
in the RMB, EMB, and CSB families and illustrated as Behavior Trees in the
[Behavior Logic](../behavior_logic/index.md) section.

**The protocol says what messages mean. The behavior logic says when to send
them.**

For example: a participant whose report transitions to *Accepted* should emit
a Report Accepted notification. Most of this is automatable; the reference
implementation handles it. But some decisions cannot be automated — these are
**call-out points**, explicit seams in the behavior trees where the protocol
hands control back to a human, a policy engine, or an external service.

!!! info "Call-out point shapes"

    Each call-out point in the Vultron behavior trees has one of five
    interaction shapes:

    | Shape | What it does |
    |---|---|
    | **Sentinel** | Watches for a condition; fires a protocol trigger when met |
    | **Evaluator** | Makes a structured decision and records a recommendation |
    | **Retriever** | Fetches external data (e.g., assigns a CVE ID) |
    | **Composer** | Generates content (e.g., drafts an advisory) |
    | **Actuator** | Causes a side effect in an external system |

    Call-out points are *by design* — the protocol cannot decide for you
    whether to accept a report, how long an embargo should last, or whether
    an advisory is ready to publish. These are the judgment calls that
    belong to your organization or your stakeholders.

### 3. Diplomatic — Shared Vocabulary for Embargo and Trust

CVD coordination breaks down most often not because of technical failure
but because parties have different unstated assumptions: when does the
embargo start? Who can invite additional participants? What happens if
someone drops out?

Vultron provides a shared vocabulary for these negotiations: explicit
Embargo state transitions (Proposed → Active → Revise → eXited), formal
invite/accept/reject handshakes, and a trust bootstrap mechanism for
establishing relationships between previously unknown parties. This
*diplomatic* layer is what allows distrusting parties to coordinate
without a central authority.

### 4. Coordinative — Enabling Ad-Hoc Interoperability

Taken together, the three preceding layers create a fourth property: any
Vultron-compatible system can join a CVD case with any other
Vultron-compatible system without bespoke setup. A new participant can
receive a case invitation, seed its local replica from the canonical
ledger, and participate in state coordination — all via the shared protocol.

This is the value proposition for adopters: you implement Vultron once, and
you gain interoperability with every other Vultron-compatible participant.

## What Conformance Means for Your System

A Vultron-compatible system operates at one or more conformance levels:

| Level | Name | What it requires |
|---|---|---|
| **L1** | Syntax | Well-formed messages — correct wire format, valid AS2 structure |
| **L2** | Semantic | Correct state transitions in response to received messages |
| **L3** | Behavioral | The right observable outputs — right messages, right order, given state conditions |

The reference implementation (this repository) demonstrates L1–L3 compliance.
You can run it as a test peer to verify your own implementation, or use it as
a starting point and replace the components your organization already has.

An L1-only implementation can exchange structured data. An L2+ implementation
participates correctly in shared case state. L3 is where the behavioral
automation lives — where Vultron begins to reduce coordination overhead
compared to email and bespoke tools.

## What Vultron Is Not

!!! note "Work in progress"

    Vultron is **not yet ready for production use**. The protocol design and
    reference implementation are under active development.

Vultron is **not** a drop-in replacement for:

- *Tracking systems* — Bugzilla, Jira, ServiceNow
- *CVD and threat coordination tools* — VINCE, MISP
- *Vulnerability disclosure platforms or programs* — HackerOne, Bugcrowd, DC3
  VDP

Instead, Vultron is designed to serve as a *lingua franca* for exchanging case
coordination data *between* those systems. It is meant to be a feature set
that existing products can adopt to gain interoperability — not a product in
itself.

Vultron is also **not** a vulnerability prioritization tool, though it is
designed to be compatible with schemes like
[SSVC](https://github.com/CERTCC/SSVC){:target="_blank"} and
[CVSS](https://www.first.org/cvss/){:target="_blank"} at its call-out points.

## Where to Go Next

Your starting point depends on what you need:

<div class="grid cards" markdown>

- :material-shield-search:{ .lg .middle } **CVD Practitioner**

    ---

    You coordinate disclosures and want to understand how Vultron models the
    process.

    [:octicons-arrow-right-24: Background](index.md) →
    [:octicons-arrow-right-24: Process Models](../process_models/index.md) →
    [:octicons-arrow-right-24: Behavior Logic](../behavior_logic/index.md)

- :fontawesome-solid-building:{ .lg .middle } **Systems Architect**

    ---

    You are evaluating whether to implement Vultron in your organization's
    tools. Start with the formal protocol and implementation guidance.

    [:octicons-arrow-right-24: Formal Protocol](../../reference/formal_protocol/index.md) →
    [:octicons-arrow-right-24: How-to Guides](../../howto/index.md)

- :fontawesome-solid-code:{ .lg .middle } **Tool Builder**

    ---

    You are implementing the wire format or integrating with an existing
    Vultron node.

    [:octicons-arrow-right-24: How-to Guides](../../howto/index.md) →
    [:octicons-arrow-right-24: Reference](../../reference/index.md)

- :material-source-pull:{ .lg .middle } **Vultron Contributor**

    ---

    You want to run the reference implementation, explore the codebase, or
    contribute.

    [:octicons-arrow-right-24: Tutorials](../../tutorials/index.md) →
    [:octicons-arrow-right-24: Reference](../../reference/index.md)

</div>
