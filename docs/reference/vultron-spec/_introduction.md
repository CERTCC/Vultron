## 1. Introduction [I]

### 1.1 Background and Motivation

A vulnerability divides the world into two sets: those who know about it, and
those who do not. From the moment of discovery, every party in the knowing
set must answer two questions repeatedly: what action should I take, and who
else needs to know what, and when? The CVD process continues until the answer
to both questions is "nothing" and "nobody."

Multi-Party CVD (MPCVD) is CVD involving three or more independent
organizations with different interests and roles. A reporter submits a
vulnerability to a vendor and a coordinator. The coordinator notifies
additional vendors. Each vendor develops its own fix on its own timeline.
All parties negotiate an embargo and coordinate disclosure. The coordination
problem scales with the number of parties; ad-hoc email and informal handoffs
do not.

Vultron addresses that gap. It provides a formal protocol that lets any number
of organizations coordinate vulnerability disclosure without a central
authority. Each participant maintains its own state and communicates through
structured messages. No single party owns the case; the Case Actor (see [§5.4.1](index.md#541-single-writer-authority)) holds
coordination authority for a specific case, and that authority is transferable.

The protocol models coordination state across four dimensions: report lifecycle
(RM), embargo status (EM), case observable state (CS), and per-participant
embargo consent (PEC). Messages are ActivityStreams 2.0 Activities, sent
asynchronously over HTTP. Participants advance their own state and announce
transitions to others. No synchronous round-trips are required.

!!! info "See also"
    - [CVD as a Coordination Problem](../../topics/background/index.md)
    - [What Does Success Mean in CVD?](../../topics/background/cvd_success.md)
    - [The Need for Interoperability](../../topics/background/interoperability.md)
    - [CERT Guide to Coordinated Vulnerability Disclosure](https://certcc.github.io/CERT-Guide-to-CVD)

### 1.2 Design Goals

**Decentralized, actor-local state.** Each participant maintains its own
replica of case state. No central authority owns all case data. The Case Actor
holds write authority for the canonical ledger, but that authority is a role
assigned to a specific participant — not a permanent, fixed service.

**Asynchronous, message-driven coordination.** No synchronous round-trips are
required. Participants advance their own state machines and announce transitions
to others via ActivityStreams Activities. A participant that is temporarily
offline does not block other participants from progressing.

**Extensible role model.** Roles are not exclusive. A participant may hold
Reporter, Vendor, and Coordinator simultaneously. New roles can be added
without breaking existing implementations. The set of protocol-authority roles
(Case Owner, Case Manager) is separate from the set of operational roles.

**Interoperable wire format.** ActivityStreams 2.0 is the normative wire
vocabulary. This choice reuses an established open standard, enables
ActivityPub-based delivery, and gives implementers a large ecosystem of
compatible tooling.

### 1.3 Relationship to Existing Standards

**ActivityStreams 2.0 / ActivityPub.** Vultron uses the ActivityStreams 2.0
vocabulary as its wire format. ActivityPub HTTP delivery is the anticipated
transport. Full ActivityPub conformance (inbox/outbox HTTP, WebFinger, HTTP
Signatures) is not currently required, but a future version of this
specification is expected to raise that floor.

**ISO/IEC 29147 and 30111.** ISO 29147 specifies vulnerability disclosure
practices; ISO 30111 specifies vulnerability handling processes. Vultron
implements the multi-party coordination layer those standards describe at a
high level. The CERT Guide to Coordinated Vulnerability Disclosure provides
the practitioner-level complement.

!!! info "See also"
    - [ISO Crosswalks](../iso_crosswalks/index.md)
    - [CERT Guide to Coordinated Vulnerability Disclosure](https://certcc.github.io/CERT-Guide-to-CVD)

### 1.4 Document Conventions

This specification uses the key words defined in
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119): **MUST**, **MUST NOT**,
**REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**,
**RECOMMENDED**, **MAY**, and **OPTIONAL**.

Sections marked `[N]` are normative. Sections marked `[I]` are informative.
Sections marked `[N/I]` contain a mix; normative requirements are explicitly
flagged.

State diagrams and transition tables use the notation defined in the
[Notation Reference](../notation.md).

---
