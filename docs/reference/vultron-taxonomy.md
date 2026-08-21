---
title: "Vultron Concept Taxonomy"
status: active
description: >
  Reference definitions for the distinct concepts that together constitute
  Vultron. Use this document to understand what each named concept covers,
  what it excludes, and how the concepts relate to each other.
---

# Vultron Concept Taxonomy

The name "Vultron" covers several distinct concepts.
Each concept has a defined scope, and each plays a different role.
This document names each concept, defines its scope, and describes the relationships between them.

!!! note "Audience"
    This document addresses four audiences: sponsors, collaborators, independent
    implementers, and contributors to this codebase. The concepts are the same
    for all four audiences. The language used to describe them may vary by
    context.

---

## Quick Reference

| Concept | One-line definition |
|---|---|
| [vultron-core](#vultron-core) | The abstract protocol: state machines, transitions, and process logic |
| [vultron-wire](#vultron-wire) | The message format: AS2 vocabulary plus semantic mapping |
| [vultron-transport](#vultron-transport) | The delivery mechanism: how messages move between participants |
| [Vultron capability sets](#vultron-capability-sets) | The named groups of capabilities that define participation levels and roles |
| [Capability shapes](#capability-shapes) | The taxonomy of optional, pluggable capability patterns |
| [Vultron roles](#vultron-roles) | Case-level participation assignments for actors |
| [Vultron-enabled applications](#vultron-enabled-applications) | Systems and components built on top of Vultron |

---

## Protocol Concepts

These three concepts define the protocol itself.
They are independent of any specific implementation language.

### vultron-core

**Definition.** The abstract Vultron protocol: the state machines (RM, EM, PEC, VFD, PXA), the valid transitions between states, the process logic that drives those transitions, and the behavioral conformance rules that define correct observable behavior.

**What is in scope.**

- The five state machines and their transition tables
- The behavioral conformance specifications (RMB, EMB, CSB) that state correct outputs for given inputs
- The ordering and cascade rules between dimensions (for example, when an EM transition must trigger a PEC bulk update)
- The process model: how N independent participants coordinate through message passing

**What is out of scope.**

- The Python module `vultron/core/` — that is the reference implementation of this concept, not the concept itself
- The behavior trees — those are one valid mechanism for executing vultron-core, not a required part of it
- The message format — that is vultron-wire
- The delivery mechanism — that is vultron-transport

**Relationship to other concepts.**

- vultron-wire carries the semantic meaning that vultron-core defines.
- vultron-transport moves vultron-wire messages between participants.
- The behavioral conformance specifications (RMB, EMB, CSB) are part of the vultron-core capability set. They are not a separate layer.
- An implementation of vultron-core is a "coordination engine" for CVD. That label describes what the implementation does, not a separate concept.

!!! note "Implementation note (reference only)"
    In the Python reference implementation, vultron-core maps to the `vultron/core/`
    module: the hexagonal inner circle that has no imports from the wire or adapter
    layers. This mapping is specific to the reference implementation and does not
    constrain how vultron-core is implemented in other languages.

---

### vultron-wire

**Definition.** The Vultron message format: the ActivityStreams 2.0 vocabulary for Vultron activities and objects, and the semantic mapping that assigns a protocol meaning to each activity type and payload combination.

**What is in scope.**

- The AS2 vocabulary: the set of valid activity types and object types defined by the Vultron protocol
- The JSON schemas that define conformant message structure
- The semantic mapping: "this activity type with this payload carries this protocol meaning"
- The boundary is the serialized JSON output. What a conformant message looks like as JSON is vultron-wire. How that JSON is produced (for example, by Pydantic models) is not.

**What is out of scope.**

- The Pydantic model classes in the reference implementation — those produce vultron-wire output, but they are not vultron-wire itself
- Valid message sequences and ordering — those are a vultron-core concern, because they emerge from the state machines
- How messages are delivered — that is vultron-transport

**Relationship to other concepts.**

- vultron-wire conformance without vultron-core conformance has limited use. A system can produce well-formed messages but cannot participate meaningfully if it does not implement the state machines.
- Partial conformance claims are possible: "I conform to these sequences in core via wire, but not those others."
- vultron-transport carries vultron-wire messages. The message schema is transport-agnostic.

!!! note "Name under review"
    "Wire" implies delivery to some readers. Candidate renames include "vultron-messages"
    and "vultron-vocabulary." No decision has been made. See [open ideas](#open-ideas).

---

### vultron-transport

**Definition.** The delivery layer: the mechanisms by which vultron-wire messages move between participants.

This concept is analogous to TAXII in the STIX/TAXII pairing, where STIX is the data format and TAXII is the transport protocol.

**What is in scope.**

- The REST (HTTP) delivery profile: how endpoints are structured, how messages are sent and received
- The ActivityPub federation profile: inbox/outbox semantics, HTTP Signatures, actor addressing
- Participant discovery: how a participant finds other Vultron actors (webfinger is the anticipated mechanism, consistent with its use alongside ActivityPub in systems such as Mastodon)

**What is out of scope.**

- Message format and semantic meaning — those are vultron-wire
- Protocol routing rules (for example, the single-writer rule and the requirement that all case-scoped messages route through the Case Actor) — those are vultron-core rules that apply at the protocol layer, not the transport layer

**Relationship to other concepts.**

- vultron-transport carries vultron-wire messages. The same JSON payload is deliverable over REST or ActivityPub.
- The routing topology rule (Participant → Case Actor → all Participants) is a vultron-core protocol rule. It governs message routing regardless of which transport is in use.

!!! note "Current status"
    The REST profile is in use in the reference implementation. The ActivityPub
    federation profile is planned (see issue #2068). Participant discovery via
    webfinger is anticipated but not yet specified.

---

## Capability Concepts

These concepts describe what a Vultron implementation or component can do.

### Vultron capability sets

**Definition.** A capability set is a named group of capabilities that defines what an actor must be able to do for a given participation level or role.
A capability is one specific thing a system can do within the Vultron protocol.

#### The Observer capability set

**The Observer capability set is the participation floor.**
Every actor that participates in any Vultron case must implement it.

There is no sub-Observer participation level.
Even a monitoring-only actor must track embargo state (PEC) to know what it is permitted to display.

The Observer capability set includes:

- Track all five state machines (RM, EM, PEC, VFD, PXA)
- Embargo compliance: accept and decline embargo invitations; track PEC state
- Receive and process all Vultron message types
- Report PXA observations (public awareness, exploit public, attacks observed)

No VFD drive obligations are part of the Observer set.
Those belong to role extension sets.

#### Role extension sets

Every CVD process role is the Observer capability set plus a role-specific extension.

| Role | Extension capabilities (added to Observer) |
|---|---|
| Reporter | Initiate cases; drive RS (report submission) |
| Vendor | Drive fix-ready VFD transition (f→F, CF) |
| Deployer | Drive fix-deployed VFD transition (d→D, CD) |
| Coordinator | Drive case participant management; coordinate multi-party disclosure |
| CNA | Assign CVE IDs directly |

Only an actor that holds both Vendor and Deployer can drive the full fix path.
Vendor alone cannot drive fix deployment.
Deployer alone cannot drive fix readiness.

#### The Authority capability set

The Authority capability set defines Case Owner governance capabilities:

- Adopt status updates without an external approval gate
- Drive shared EM transitions
- Transfer case ownership

The Authority capability set is separable from the Hosting capability set.
A human Coordinator can hold Authority while a service actor performs Hosting.

#### The Hosting capability set

The Hosting capability set defines Case Manager infrastructure capabilities:

- Host a Case Actor (the single-writer for the canonical ledger)
- Maintain the authoritative append-only case ledger
- Replicate ledger entries to participants via `Announce(CaseLedgerEntry)`
- Manage case participants (invitation, role assignment, removal)

The Hosting capability set is separable from the Authority capability set.
A platform can provide Hosting without holding governance authority.

#### Named configurations

Common combinations of capability sets have names because they describe real deployment patterns.

| Configuration | Capability sets |
|---|---|
| **Hosting Coordinator** (or Autonomous Coordinator) | Observer + Coordinator role + Authority + Hosting |
| **Self-coordinating Vendor** | Observer + Vendor role + Deployer role + Authority + Hosting |
| **Bug Bounty Platform** | Observer + Hosting (Authority is optional) |

A Hosting Coordinator is a `type:service` actor that holds both `CASE_OWNER` and `CASE_MANAGER` roles.
It decides (Authority) and executes (Hosting) without a separate human approval step.

#### Optional domain capability sets

Optional capabilities are organized by domain function.

Examples of domain capability sets:

- **CNA capabilities** — assign CVE IDs (typically Actuator shape, calling the CVE assignment API)
- **Prioritization capabilities** — assess report severity or priority (typically Evaluator or Retriever shape)
- **Exploit detection capabilities** — detect or assess exploit availability (typically Sentinel or Retriever shape)

A capability set name describes business function.
A [capability shape](#capability-shapes) describes the technical connection contract.
These two dimensions are orthogonal: the same domain set may use multiple shapes.

**A conformance claim names capability sets and roles directly.**
Examples: `Observer / Vendor`, `Observer + Authority + Hosting / Coordinator + Case Owner`.

**What is in scope.**

- All protocol behaviors a system can implement, required or optional
- Named capability sets as defined groupings of required capabilities
- Optional domain capability sets organized by business function

**What is out of scope.**

- The conformance test layers (L1–L4) — those describe what a test verifies, not what a system provides.
  Capability sets and test layers are orthogonal.

**Relationship to other concepts.**

- Capability shapes provide the technical contract taxonomy for optional capabilities.
- Vultron roles use capability sets to define prerequisites for role assignment.

---

### Capability shapes

**Definition.** The taxonomy of optional, pluggable capability patterns. Each capability shape defines a contract for a specific category of automation that can connect to the behavior engine at a call-out point.

**Previous name.** This concept was previously named "agent shapes" or "coordination agent taxonomy." That name was accurate when written. It is now replaced because "agent" has acquired strong connotations of LLM-based autonomous systems, which was not the original intent. "Capability shape" describes what the concept actually covers: the pattern that a capability takes.

**The five capability shapes.**

| Shape | What it does | Connection type |
|---|---|---|
| **Sentinel** | Monitors a condition. Returns success or failure with no side effects. Used as a precondition guard. | Call-in surface (no call-out point node) |
| **Evaluator** | Receives a situation and a set of options. Returns a structured recommendation. Gates downstream execution. | Call-out point |
| **Retriever** | Receives a query. Returns structured facts from an external source. | Call-out point |
| **Composer** | Receives context. Generates and records a new content artifact. | Call-out point |
| **Actuator** | Receives a trigger. Invokes an external system for a side effect. Confirms success or failure. Produces no content artifact. | Call-out point |

A capability shape defines the contract. A concrete implementation that satisfies the contract is a Vultron-compatible capability of that shape.

**What is in scope.**

- The five shapes and their contracts (what each shape accepts and returns)
- The classification rule for each shape

**What is out of scope.**

- The specific technology used to fulfill a shape (a shape may be fulfilled by a human, an automated script, an LLM, or any other mechanism)
- The Fuzzer Node — that is a simulator-layer stub that occupies a call-out point until a real capability is wired in; it is not a capability shape itself

**Relationship to other concepts.**

- Capability shapes are orthogonal to capability sets. An Observer implementation may have zero capability shapes implemented. A Sentinel capability does not require anything beyond what the host behavior engine provides.
- Capability shapes are the taxonomy for the optional capabilities in [Vultron-compatible capabilities](#vultron-compatible-capabilities).
- In the reference implementation, a capability shape maps to a Port (abstract interface). A concrete capability implementation maps to an Adapter. This mapping is specific to the hexagonal architecture of the Python codebase and is not required of other implementations.

---

## Participation Concepts

### Vultron roles

**Definition.** Case-level participation assignments. A role describes what an actor is doing in a specific case.

Roles are not properties of systems. They are assignments within a case.

**Two categories of roles.**

**Process roles** define what an actor does within a case and which protocol transitions it is authorized to drive.

| Role | Drive authority |
|---|---|
| Reporter | Initiates cases; drives RS (report submission) |
| Vendor | Drives its own VFD fix-ready transition (CF) |
| Deployer | Drives its own VFD fix-deployed transition (CD) |
| Coordinator | Drives case participant management; coordinates multi-party disclosure |
| CNA | May directly assign CVE IDs |
| Observer | No VFD drive obligations; may report PXA observations |

**Protocol authority roles** define what an actor controls in the protocol machinery.

| Role | Protocol authority |
|---|---|
| Case Owner | Authoritative decision-maker for a case |
| Case Manager | AS actor performing case replica synchronization on behalf of the Case Owner |

**Role assignment.**

Roles are assigned, not self-declared.

1. A case starts with a Case Owner (the actor who initiated the case).
2. The Case Owner may delegate the Case Manager role to another actor.
3. The Case Manager designates other actors into process roles.

Self-assignment is not permitted. This rule prevents an actor from declaring a role (for example, Coordinator) on a case it is not ready to coordinate.

**Capabilities and roles.**

The relationship between capabilities and roles is bidirectional.

- Capabilities are a prerequisite for a role. Having the right capabilities means an actor can perform the role. It does not mean the actor automatically holds the role.
- Holding a role in a case means other participants expect the actor to have the capabilities that role requires.

**What is in scope.**

- The two categories of roles and their definitions
- The assignment chain (Case Owner → Case Manager → others)
- The bidirectional relationship between capabilities and roles

**Relationship to other concepts.**

- A role claim creates capability expectations. If an actor holds the Coordinator role, other participants expect it to have the Coordinator role extension set.
- The Observer capability set is the minimum protocol floor for case participation. Role extension sets add further expectations on top of that floor.

---

## Ecosystem Concepts

### Vultron-enabled applications

**Definition.** Systems and components built using Vultron. This concept covers the full range: end-user applications, coordination automation components, and the reference implementation itself.

**Examples.**

- A PSIRT portal that uses the Vultron protocol to manage vulnerability cases — this implements vultron-core, vultron-wire, and vultron-transport, and holds process roles within its cases.
- A Sentinel component that monitors threat feeds and reports PXA observations into a case — this implements a capability shape and is a Vultron-compatible capability.
- The Python reference implementation in this repository — this implements the full stack: vultron-core, vultron-wire, vultron-transport, and some capability shapes.

**What is in scope.**

- Any system that implements one or more Vultron protocol concepts
- Coordination automation components (implementations of capability shapes)
- Full-stack implementations that participate in CVD coordination

**What is out of scope.**

- The protocol itself — that is vultron-core, vultron-wire, and vultron-transport
- Systems that merely cite or reference Vultron without implementing it

**Relationship to other concepts.**

- A Vultron-enabled application that implements vultron-core, vultron-wire, and vultron-transport at the Observer level or above is a "coordination engine" in the sense that it can coordinate CVD cases. That label is descriptive vocabulary for what the application does, not a separate taxonomy concept.

---

## Architectural Views

Three architectural views are planned for this taxonomy. Each view answers a different question.

### View 1 — Layered module view

This view answers the question: what are the layers of Vultron, and how do they depend on each other?

The layers, from lowest to highest:

1. **vultron-core** — the protocol foundation. All other layers depend on vultron-core.
2. **vultron-wire** — the message format layer. Translates vultron-core protocol meanings into serialized messages.
3. **vultron-transport** — the delivery layer. Carries vultron-wire messages between participants.
4. **Capability shapes** — the integration surface. Sits at the boundary between the protocol engine and optional automation. Capability shapes are defined by vultron-core (the call-out points) and implemented by Vultron-compatible capabilities.
5. **Vultron-enabled applications** — the top layer. Uses all lower layers to participate in CVD coordination.

Vultron roles and Vultron-compatible capabilities are not layers. They describe aspects of participation and implementation, respectively, that apply across the full stack.

### View 2 — Peer-to-peer component-and-connector view

This view answers the question: how do two Vultron participants communicate?

This view is planned and not yet drawn. It will show:

- How two participants exchange vultron-wire messages over vultron-transport
- How the Case Actor mediates all case-scoped messages
- How case state replicates from the Case Actor to participants via ledger entries
- Where capability shapes connect to the behavior engine

### View 3 — Conformance view (custom)

This view answers the question: what do I need to build to claim a specific conformance level or role?

This view is planned and not yet drawn. It will show:

- A capability set matrix: rows are named capability sets (Observer, role extensions, Authority, Hosting, domain sets); columns are role or configuration claims; cells show required versus optional
- Role overlays showing which capability sets each role requires
- Named configuration profiles as pre-filled columns in the matrix

---

## Open Ideas

These questions are noted for future resolution. They do not block use of this taxonomy.

1. **vultron-wire name review.** "Wire" implies delivery to some readers. Candidate renames: "vultron-messages," "vultron-vocabulary." No decision has been made. Log as a GitHub issue when ready to decide.

2. **vultron-transport: discovery scope.** Participant discovery via webfinger is anticipated as part of vultron-transport. It is not yet specified. Related to ActivityPub federation work (issue #2068).

3. **Role capability prerequisites.** The full mapping of which capabilities each role extension set requires is not yet specified. The conformance view (above) will address this when drawn.

4. **Named configurations: canonical name.** "Hosting Coordinator" and "Autonomous Coordinator" are both in use. A decision on the canonical name is needed.

---

## Dissolved Concepts

These labels were candidates for this taxonomy but did not survive review.

| Label | Outcome |
|---|---|
| vultron-behaviors | Dissolved. The behavioral conformance specifications (RMB, EMB, CSB) are part of vultron-core. "Behavior trees" are one implementation mechanism for vultron-core, not a separate taxonomy concept. |
| coordination engine | Demoted to descriptive vocabulary. A Vultron-enabled application that implements vultron-core at the Observer level or above is a "coordination engine" for CVD. This label describes what the application does, not a separate concept. |
| T0 / Consumer | Dropped. A parse-only entity has nothing useful to do with Vultron data if it cannot honor embargoes. Observer is the participation floor. |
| T1 / Participant | Collapsed into the Observer capability set. |
| T2 / Coordinator | Split into three separable concepts: Coordinator role extension set, Authority capability set, and Hosting capability set. |
| T0/T1/T2 tier notation | Eradicated. Conformance claims name capability sets and roles directly. Example: `Observer / Vendor` replaces `T1 / Vendor`. |

---

## Related Documents

- [Glossary](glossary.md) — domain terminology for the Vultron protocol and reference implementation
- [Draft Vultron Protocol Specification](draft-vultron-spec.md) — normative protocol specification including capability sets and role taxonomy
- ADR-0024 — Coordination Agent Taxonomy (original "agent shapes" decision; capability shapes is the updated name)
- ADR-0038 — Four-Tier Specification Taxonomy (how specification files are classified)
