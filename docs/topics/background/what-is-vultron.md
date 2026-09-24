---
description: >
  What kind of thing Vultron is: an open protocol that lets the systems
  organizations already use for vulnerability disclosure coordinate a case
  with each other, the way email servers exchange mail.
stakeholder_type: ALL
level: 100
---

# What Is Vultron?

Vultron is an open protocol that lets the systems organizations already use for Coordinated Vulnerability Disclosure (CVD) coordinate a case with each other.
It is a protocol in the way the Simple Mail Transfer Protocol (SMTP) is: it defines what systems say to each other, not a product anyone must run.
Two mail services compete for users and still deliver each other's mail, because both speak SMTP.
Vultron aims for the same arrangement among vulnerability trackers, coordination services, and disclosure platforms.

{% include-markdown "../../includes/protocol_analogies.md" %}

!!! note "Work in progress"

    Vultron is **not yet ready for production use**.
    The protocol design and reference implementation are under active development.

---

## The problem it addresses

A vulnerability that spans several vendors, a coordinator, and a national Computer Security Incident Response Team (CSIRT) is a multi-party coordination problem.
Each party runs its own system: a bug tracker, a disclosure platform, a coordination service.
Those systems rarely exchange data, and when they do, it is through a point-to-point integration built for one pair of organizations.

So every new coordination relationship costs custom effort.
Participants end up with an account on each partner's system, or fall back to encrypted email and tickets updated by hand.
Vultron replaces those bilateral arrangements with one shared protocol that any tool, CSIRT, vendor, or service provider can implement.

---

## What we mean by *protocol*

!!! question inline end "Why *Vultron*?"

    The working name for the protocol is *Vultron*, an homage to the fictional robot Voltron.
    In the Voltron animated series, a team of protectors joins forces to defend the universe from their adversaries.
    Their mission requires independent defenders who coordinate their efforts to reach a shared goal.
    Like Voltron, the Vultron Protocol combines humans with the technical processes and mechanisms that empower them.
    Those humans, processes, and mechanisms must work individually and together to protect information systems, and the people who depend on them, from exploitation.

The Oxford English Dictionary gives two senses of [*protocol*](https://www.oed.com/dictionary/protocol_n?tab=meaning_and_use){:target="_blank"}, and both apply here.

!!! quote "Oxford English Dictionary on *protocol*"

    (Computing and Telecommunications) A (usually standardized) set of
    rules governing the exchange of data between given devices, or the
    transmission of data via a given communications channel.

    (In extended use) the accepted or established code of behavior in
    any group, organization, or situation; an instance of this.

The first sense covers the messages systems exchange.
The second covers how the people behind those systems are expected to behave.
Vultron separates these into four senses, and understanding all four is the fastest way to see what it can and cannot do for you.

### 1. Technical: message format and syntax

Vultron specifies a wire format based on [ActivityStreams 2.0](https://www.w3.org/TR/activitystreams-core/){:target="_blank"} for the messages CVD Participants exchange.
Those messages carry report submissions, state change notifications, embargo proposals, and invitations.
Any system can implement the wire format independently of other implementations.

This is the *syntactic* layer.
Two systems that agree at this level can exchange structured data, even if they do not yet interpret it identically.

### 2. Procedural: behavior logic

Beyond the wire format, Vultron specifies *behavioral requirements*: given a case state and a received message, what a well-behaved Participant does next.
The requirements are machine-readable specifications in the Report Management Behavioral ([RMB](../../reference/specs/protocol.md#rmb)), Embargo Management Behavioral ([EMB](../../reference/specs/protocol.md#emb)), and CVD Case State Behavioral ([CSB](../../reference/specs/protocol.md#csb)) families.
The [Behavior Logic](../behavior_logic/index.md) section illustrates them as behavior trees.

!!! note "Syntax describes meaning; behavior specifies timing"

    The wire format says what messages *mean*.
    The behavioral requirements say *when* to send them.

For example, a Participant whose report transitions to *Accepted* emits a notification that it accepted the report.
The reference implementation automates most of this.
Some decisions cannot be automated, and these are **call-out points**: explicit seams where the protocol hands a decision to a human, a policy engine, or an external service.

!!! info "Call-out points and the Sentinel pattern"

    Each call-out point takes one of four capability shapes (BT-18-013):

    | Shape | What it does |
    |---|---|
    | **Evaluator** | Makes a structured decision and returns a recommendation |
    | **Retriever** | Fetches external facts, such as whether a Common Vulnerabilities and Exposures (CVE) ID already exists |
    | **Composer** | Generates content, such as an advisory draft |
    | **Actuator** | Causes a side effect in an external system |

    A **Sentinel** is not a shape.
    It is a call-in pattern: a process that watches a condition and acts on its own initiative when it fires, instead of waiting to be asked.

    Call-out points exist by design.
    The protocol cannot decide for you whether to accept a report, how long an embargo should last, or whether an advisory is ready to publish.
    Those judgment calls belong to your organization.
    Each can be answered by an automated policy, by a person, or by a mix of the two.
    The [Capability Model](../capability_model/index.md) lists every call-out point and where your system plugs in.

### 3. Diplomatic: shared vocabulary for embargo and trust

CVD coordination breaks down more often from unstated assumptions than from technical failure.
Parties disagree about when an embargo starts, who can invite additional Participants, and what happens when someone drops out.

Vultron gives these negotiations a shared vocabulary.
Embargoes move through explicit states (Proposed, Active, Revise, eXited).
Invitations follow formal invite, accept, and reject handshakes.
A trust bootstrap mechanism lets previously unknown parties establish a relationship.
This *diplomatic* layer lets parties who do not fully trust each other coordinate without a central authority.

### 4. Coordinative: ad-hoc interoperability

The three preceding senses combine into a fourth: any Vultron-compatible system can join a case with any other Vultron-compatible system without bespoke setup.
A new Participant receives a case invitation, seeds its local copy of the case from the case ledger, and takes part in state coordination through the shared protocol.

This is the value to an adopter.
You implement Vultron once, and you can coordinate with every other Vultron-compatible Participant.

---

## What conformance means for your system

A conformance claim names the **capability sets** an implementation provides and the **roles** it takes on, written `CapabilitySet / Role` ([§12.1](../../reference/vultron-spec/index.md#121-conformance-model-overview)).
Examples are `Case Observer / Vendor` and `Case Observer + Case Decision + Case Hosting / Coordinator + Case Owner`.

| Capability set | What it adds |
|---|---|
| **Case Observer** | The participation floor: track the case's state machines, send the messages your roles require, and take part in embargo negotiation |
| **Case Decision** | Governing a case as its owner: adopting its own status updates without approval, driving shared embargo transitions, and transferring ownership |
| **Case Hosting** | Running a case for others: holding the canonical case ledger, replicating it to Participants, and managing who participates |

The normative definitions are in [§12.2 Capability Sets](../../reference/vultron-spec/index.md#122-capability-sets).

Conformance *tests* are organized in four layers, and the layers are a separate question from the capability sets ([§12.5](../../reference/vultron-spec/index.md#125-conformance-testing-approach)).
A capability set says what your software provides; a layer says what a test checks.

| Layer | What a test checks |
|---|---|
| **L1 Syntax** | Messages are well formed against the wire format |
| **L2 Semantics** | Each message drives the correct state transition |
| **L3 Behavior** | The right messages are emitted and the right states reached, given a state and a received message |
| **L4 Process** | The internal order of decisions, such as precondition before state write before side effect |

Independent implementations are tested at L1 through L3.
L4 inspects internal structure, so it applies only to the reference implementation.
You can run the reference implementation as a test peer for your own system, or start from it and replace the components your organization already has.

---

## What Vultron is not

{% include-markdown "../../includes/vultron_is_not.md" %}

---

## Where to go next

Pick the description that matches your situation.

- [You handle vulnerability reports and coordinate cases with other organizations](../../start/coordinate-cases.md)
- [You maintain a vulnerability tracker and want it to talk to your partners](../../start/connect-your-tracker.md)
- [You study how vulnerability disclosure works and want the models behind it](../../start/study-the-process.md)
- [You want to work on the Vultron reference implementation](../../start/contribute.md)
