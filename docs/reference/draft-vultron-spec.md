---
title: "Draft: Vultron Protocol Specification"
version: "2026.08.07"
status: draft
description: >
  Working draft outline of the Vultron Protocol specification, organized as
  an RFC-like document. Not yet ready for external circulation. Sections
  marked [N] are normative; [I] are informative. Source pointers indicate
  the strongest existing material for each section.
---

# Draft: Vultron Protocol Specification

!!! warning "Working Draft — not ready for external circulation"
    Completeness is uneven, deliberately so:

    - **§4 (Syntactic), §5 (Semantic), §6 (Behavioral), §7 (Conformance)** carry
      drafted normative content, grounded in `specs/` and the implementation.
      Requirements stated there are intended to be read as normative.
    - **§1–§3, §8–§10 and the Annexes** remain outline: bullet points and source
      pointers indicating where material will be drawn from.

    Where this document and the implementation disagree, the implementation is
    currently authoritative — several such disagreements were found and corrected
    in `specs/` while drafting. Open questions are listed at the end; those
    affecting normative text are flagged inline at the point of use.

---

## Abstract

Brief description of the protocol purpose: enabling coordinated vulnerability
disclosure among multiple parties through asynchronous message exchange and
shared state tracking.

---

## 1. Introduction [I]

### 1.1 Background and Motivation

- CVD as a multi-party coordination problem
- Why a protocol (vs. ad-hoc process) is needed
- Scope: MPCVD (multi-party CVD) as the target
- *Source: `docs/topics/background/`*

### 1.2 Design Goals

- Decentralized, actor-local state
- Asynchronous, message-driven coordination
- Extensible role model
- *Source: `docs/adr/` (esp. ADR-0005 AS2 vocabulary, ADR-0009 hexagonal
  architecture, ADR-0012 per-actor datalayer isolation, ADR-0019 ledger/process-log
  separation); `docs/topics/background/interoperability.md`*

### 1.3 Relationship to Existing Standards

- ActivityStreams 2.0 / ActivityPub as the wire foundation
- Relationship to CVD best practices (CERT/CC guidance, ISO 29147/30111)
- *Source: `notes/activitystreams-semantics.md`*

### 1.4 Document Conventions

- RFC 2119 key words (MUST, SHOULD, MAY, etc.)
- Notation used in state diagrams and transition tables
- *Source: `docs/reference/notation.md`*

---

## 2. Terminology [N/I]

### 2.1 Core Terms

- Vulnerability, Report, Case, Participant, Actor
- Reporter, Vendor, Coordinator, Deployer, Observer
- Case Owner vs. Case Participant
- *Source: `docs/reference/glossary.md`; `vultron/enums/roles.py` (`CVDRole`);
  `docs/_acronyms/index.md`*

### 2.2 Protocol Terms

- Message, Activity, Object, Channel
- State, Transition, Event
- Embargo, Publication
- **Protocol shorthand** — the two-letter codes (`RS`, `EP`, `CV`, …) naming
  protocol messages by meaning rather than by wire form. Introduced in §5 and
  mapped to AS2 wire forms in §5.7. Readers encountering a shorthand before §5
  may treat it as an opaque label for a message type.
- *Source: `docs/reference/formal_protocol/index.md`;
  `docs/reference/formal_protocol/messages.md`; `docs/reference/glossary.md`*

---

## 3. Protocol Overview [I]

### 3.1 The Protocol as a Communicating Hierarchical State Machine

- Brand & Zafiropulo formal definition
- N processes, disjoint state sets, message sets, successor function
- Global state as (S, C) pair
- *Source: `docs/reference/formal_protocol/index.md` (already written, near-verbatim)*

### 3.2 Tracking Dimensions

The protocol tracks coordination state across four dimensions:

- Report Management (RM): lifecycle of a report from receipt to closure
- Embargo Management (EM): negotiated disclosure timing (case-level)
- Case State (CS): multi-dimensional public knowledge state
- Participant Embargo Consent (PEC): per-participant embargo consent posture

!!! note "Four dimensions, five state machines"
    These four dimensions are realized as **five** state machines, because CS is
    a compound of two independent axes: `VFD` (participant-specific — vendor
    aware, fix ready, fix deployed) and `PXA` (participant-agnostic — public
    aware, exploit public, attacks observed). CS is the pair `(VFD, PXA)`.

    This document says "four dimensions" when discussing what is tracked, and
    "five state machines" when discussing what must be implemented (§6, §7.2).
    Both counts are correct; they count different things.

RM, EM, and CS were present in the original protocol design. PEC emerged
during implementation (see §6.4) and is fully normative.

- *Source: `docs/topics/process_models/`; `vultron/core/states/`*

### 3.3 How the Dimensions Interact

- RM drives case progression; EM gates publication; CS reflects observable reality
- PEC captures whether each individual participant has consented to the active
  embargo — EM and PEC are orthogonal: EM says whether a case has an embargo,
  PEC says whether a given participant has agreed to it
- State transitions in one dimension can trigger obligations in others (see §6.5)
- *Source: `docs/topics/process_models/model_interactions/`, `notes/protocol-event-cascades.md`,
  `notes/participant-embargo-consent.md`*

### 3.4 Participants and Roles

- Roles are not exclusive; a participant may hold multiple roles
- N = |Participants|, not |Roles|
- Two distinct categories of roles are used in this protocol (see §7.3 for the
  full taxonomy):
  - **Operational/domain roles** — what an actor *does* within a case (Reporter,
    Vendor, Coordinator, Deployer, CNA, Observer). These determine which
    protocol transitions an actor is authorized to drive.
  - **Protocol authority roles** — what an actor *controls* in the protocol
    machinery (Case Owner, Case Manager). These confer specific protocol-layer
    authority independent of domain activity.
- Role assignment and changes over case lifetime
- *Source: `docs/reference/formal_protocol/index.md` §"Number of Processes"*

---

## 4. Syntactic Layer — Wire Format [N]

### 4.1 Base Vocabulary

- Vultron messages are ActivityStreams 2.0 Activities
- Required fields: `type`, `actor`, `object`, `id`
- Extended types defined by the Vultron vocabulary namespace
- Implementations MUST use the Vultron AS2 vocabulary for message structure;
  full ActivityPub server semantics (inbox/outbox HTTP delivery, WebFinger
  discovery, HTTP Signatures) are not currently required by this specification

!!! note "Informative: ActivityPub roadmap"
    A future version of this specification is expected to raise the conformance
    floor to ActivityPub at T1 and above. Implementations built against the
    current AS2-only baseline should anticipate that re-evaluation against a
    future ActivityPub-baseline version will be required. The AS2-only profile
    may become a compatibility profile at that point. (See issue #2068.)

- *Source: `specs/vultron-as2-mapping.yaml` (VAM-01 through VAM-09)*

### 4.2 Object Types

- `VulnerabilityCase` — the shared coordination object
- `VulnerabilityReport` — the initial report artifact
- `CaseParticipant` — actor-in-role within a case
- `CaseParticipantRole` — a `CVDRole` being offered to an actor in a case
  context; introduced to make role delegation structurally distinct from case
  ownership transfer (both previously serialized as `Offer(VulnerabilityCase)`)
- `EmbargoEvent` — embargo proposal/acceptance/revision/termination records.
  This is an AS2 `Event` subtype; embargo activities therefore appear on the
  wire as `Invite(Event)`, not as a distinct embargo verb
- `CaseLedgerEntry` — an entry in the authoritative canonical case ledger; the
  unit of state replication from the Case Actor to participants
- `CaseProposal` — a proposed case, prior to case creation
- `CaseStatus` / `ParticipantStatus` — status records. **These are not
  interchangeable, and the distinction is load-bearing:**
  - `ParticipantStatus` is a *claim* — one participant's assertion about its
    own (or another participant's) state. Any participant may write one.
  - `CaseStatus` is *canonical* — the Case Actor's authoritative record of
    shared case state. Only the Case Actor may write it (§4.4).

  The transition from claim to canonical is an explicit authorization step,
  not an implementation detail; see §6.5.1.

- *Source: `vultron/wire/as2/vocab/objects/`; `specs/vocabulary-model.yaml`;
  ADR-0039 (`CaseParticipantRole`); ADR-0036 (status dimension objects)*

### 4.3 Activity Types and Canonical Message Forms

- Base AS2 verbs used by Vultron: `Create`, `Offer`, `Accept`, `Reject`,
  `Announce`, `Update`, `Add`, `Remove`, `Invite`, `Read`, `Join`, `Ignore`,
  `TentativeReject`
- Vultron-specific nested-object patterns, e.g.
  `Accept(Invite(Event)[context=VulnerabilityCase])` for embargo acceptance
- Two distinct activities govern bringing an actor into a case, and they are
  **not** the same message:
  - `Invite[target=VulnerabilityCase]` — the Case Actor invites an actor to
    join, on the Case Owner's behalf. Answered with `Accept(Invite)` or
    `Reject(Invite)`.
  - `Offer(CaseParticipant)` — the *suggest-actor* path: a participant
    proposes that some actor be brought into the case. Answered by the Case
    Owner, which may then cause an `Invite` to be emitted.

  Both paths converge on `Accept(Invite)`, but they originate differently and
  carry roles differently. Conflating them erases the suggest-actor round-trip.

- Implementation semantic mappings are defined in
  `vultron/core/models/events/base.py` (`MessageSemantics` enum); this is the
  authoritative source for which AS2 patterns correspond to which protocol
  operations. The protocol-shorthand → semantic → wire-form mapping table is
  given in §5.7, after the shorthands themselves have been introduced.
- *Source: `specs/vultron-as2-mapping.yaml` (VAM-01–VAM-09);
  `specs/message-semantics-mapping.yaml` (MSM-01–MSM-03); ADR-0039*

### 4.4 Addressing and Channels

- Actor URIs as process identifiers (aligned with ActivityPub actor model)
- Inbox/outbox as the delivery model: each actor exposes an inbox (receive)
  and outbox (send/broadcast)

#### 4.4.1 Single-Writer Authority

The Case Actor is the **only** entity authorized to mutate shared case state —
the CS `PXA` axis, the EM state, the embargo record, and the case ledger. No
participant and no use-case handler may write shared case state directly; all
such mutations MUST route through the Case Actor.

The participant-specific axes (`RM`, `VFD`) are owned by each participant's own
`CaseParticipant` record and are explicitly **not** subject to this restriction —
a participant is the authority on its own RM and VFD state.

This single-writer rule is the axiom from which the routing topology below
follows. It exists to prevent concurrent-write races and to ensure every shared
state change passes through the Case Actor's consistency checks.

- *Source: `specs/vultron-protocol-spec.yaml` VP-17-001*

#### 4.4.2 Routing Topology

Once a case exists, all case-scoped participant messages MUST follow this path:

```text
Participant → Case Actor → CaseLedgerEntry → Announce(CaseLedgerEntry) → all Participants
```

- A participant MUST address case-scoped activities to the Case Actor only.
- A participant **MUST NOT** deliver a case-scoped message directly to another
  participant's inbox. Delivery MUST be mediated by the Case Actor and recorded
  in the case ledger before fan-out.
- `Announce(CaseLedgerEntry)` is the **only** mechanism by which participants
  learn of accepted case-state changes.

There are exactly **two** exceptions, both confined to case bootstrap, both
occurring before the Case Actor is available as an intermediary:

1. **Pre-case report submission** — the Reporter sends `Offer(VulnerabilityReport)`
   directly to the Vendor. No case, and therefore no Case Actor, exists yet.
2. **Case creation handshake** — the receiving party sends
   `Create(VulnerabilityCase)` to the Reporter to introduce the Case Actor. This
   is the trust-bootstrap exchange (§5.5).

After case creation, no direct participant-to-participant messaging is
permitted.

!!! note "Informative: why centralize"
    Routing through a single writer avoids the complexity of a distributed
    ledger while preserving actor-local state: each participant still maintains
    its own replica and its own view. The cost is that the Case Actor is a
    single point of coordination authority, and its availability bounds case
    progress. This is a deliberate trade-off, not an incidental property of the
    current implementation — but note that the *requirements* above are
    normative regardless of how one weighs the trade-off.

- *Source: `specs/vultron-protocol-spec.yaml` VP-18-001, VP-17-001;
  `specs/outbox.yaml` (OX-01–OX-12); `notes/case-communication-model.md`;
  `notes/peer-broadcast-failure-semantics.md`*

### 4.5 Serialization

- JSON-LD as the normative serialization
- Required context declarations
- *Source: AS2/ActivityPub standards; `specs/message-validation.yaml`*

---

## 5. Semantic Layer — Message Meanings [N]

Protocol messages are referred to by two-letter shorthands throughout this
specification. The shorthand names a *protocol meaning*; §5.7 maps each
shorthand to its AS2 wire form.

!!! note "Error and acknowledgement messages: read §5.6 first"
    Several messages below are part of the formal protocol definition but have
    **no wire representation** in the current semantic registry. §5.6 states
    which, and why. Implementers should read that subsection before treating any
    `*E` or `*K` shorthand as dispatchable.

### 5.1 Report Management Messages

$M^{rm} = \{RS, RI, RV, RD, RA, RC, RK, RE\}$

| Shorthand | Name | Meaning |
|---|---|---|
| `RS` | Report Submission | A report is sent to a new participant |
| `RI` | Report Invalid | Sender has designated the report invalid |
| `RV` | Report Valid | Sender has designated the report valid |
| `RD` | Report Deferred | Sender is deferring further action |
| `RA` | Report Accepted | Sender has accepted the report for further action |
| `RC` | Report Closed | Sender has closed the report |
| `RK` | Report Acknowledgement | Acknowledges receipt of any RM message above |
| `RE` | Report Error | Sender received an unexpected RM message (see §5.6) |

All RM state changes are reported from the **sender's** perspective, not the
recipient's. `RS` is the only RM message whose *receipt* directly drives an RM
state change in the receiver; the rest inform the receiver about the sender.

Unlike the other acknowledgement shorthands, `RK` **is** a dispatchable message:
it maps to `MessageSemantics.ACK_REPORT` with wire form
`Read(Offer(VulnerabilityReport))`.

- *Source: `docs/reference/formal_protocol/messages.md`;
  `specs/message-semantics-mapping.yaml` MSM-01; `specs/vultron-protocol-spec.yaml` VP-03*

### 5.2 Embargo Management Messages

$M^{em} = \{EP, ER, EA, EV, EJ, EC, ET, EK, EE\}$

Nine messages, in three related groups. Note that the *initial-proposal* and
*revision* groups are distinct shorthands:

| Shorthand | Name | Meaning |
|---|---|---|
| `EP` | Embargo Proposal | Proposed embargo terms |
| `ER` | Embargo Proposal **Rejection** | Sender rejected an embargo proposal |
| `EA` | Embargo Proposal Acceptance | Sender accepted an embargo proposal |
| `EV` | Embargo **Revision** Proposal | Proposed revision to existing terms |
| `EJ` | Embargo **Revision** Rejection | Sender rejected a proposed revision |
| `EC` | Embargo **Revision** Acceptance | Sender accepted a proposed revision |
| `ET` | Embargo Termination | Sender terminated the embargo; immediate effect |
| `EK` | Embargo Acknowledgement | Acknowledges any EM message above (see §5.6) |
| `EE` | Embargo Error | Sender received an unexpected EM message (see §5.6) |

!!! warning "`EV`/`EJ`/`EC` are wire-identical to `EP`/`ER`/`EA`"
    The revision shorthands share their AS2 wire forms with their
    initial-proposal counterparts. The distinction is **not** encoded in the
    activity structure.

    An implementation MUST infer revision-versus-initial context from **local EM
    state**: a proposal arriving while EM is `ACTIVE` or `REVISE` is a revision
    (`EV`); the same wire message arriving while EM is `NONE` or `PROPOSED` is an
    initial proposal (`EP`).

    This is a genuine interoperability hazard. An implementation that treats the
    wire form as self-describing will mis-handle every revision.

If early termination is desired but the termination time is in the future, that
SHOULD be expressed as an `EV` (revision proposal) rather than an `ET`, since
`ET` takes immediate effect.

Tacit acceptance semantics are specified in §6.2.2.

- *Source: `docs/reference/formal_protocol/messages.md`;
  `specs/message-semantics-mapping.yaml` MSM-02 (esp. MSM-02-003/004/005);
  `specs/embargo-policy.yaml`; `notes/embargo-lifecycle.md`;
  `notes/embargo-default-semantics.md`*

### 5.3 Case State Messages

$M^{cs} = \{CV, CF, CD, CP, CX, CA, CK, CE\}$

| Shorthand | Name | CS axis | Meaning |
|---|---|---|---|
| `CV` | Vendor Awareness | VFD (`v→V`) | A report has been delivered to a specific Vendor |
| `CF` | Fix Readiness | VFD (`f→F`) | A specific Vendor has a fix ready |
| `CD` | Fix Deployment | VFD (`d→D`) | A fix has been deployed |
| `CP` | Public Awareness | PXA (`p→P`) | The vulnerability is publicly known |
| `CX` | Exploit Public | PXA (`x→X`) | An exploit has been published |
| `CA` | Attacks Observed | PXA (`a→A`) | Attacks exploiting the vulnerability are observed |
| `CK` | CS Acknowledgement | — | Acknowledges any CS message above (see §5.6) |
| `CE` | CS Error | — | Sender received an unexpected CS message (see §5.6) |

All six status shorthands (`CV`–`CA`) share a single wire form and semantic:
`Add(CaseStatus)[target=VulnerabilityCase]` →
`MessageSemantics.ADD_CASE_STATUS_TO_CASE`. **The specific transition is encoded
in the object payload, not in the activity type.** An implementation dispatching
on activity type alone cannot distinguish `CF` from `CA`.

Receiving a CS message updates the receiver's model of the **sender's** CS state;
it does not change the receiver's own CS state. See §6.3.4.

- *Source: `docs/reference/formal_protocol/messages.md`;
  `specs/message-semantics-mapping.yaml` MSM-03; `specs/cs-behavior.yaml` CSB-01–CSB-04*

### 5.4 Case Coordination Messages

- `Create(VulnerabilityCase)` — case initiation
- `Invite[target=VulnerabilityCase]` / `Accept(Invite)` / `Reject(Invite)` —
  invitation lifecycle (Case Actor invites on the Case Owner's behalf)
- `Offer(CaseParticipant)` / `Accept(Offer(...))` / `Reject(Offer(...))` —
  suggest-actor lifecycle (a participant proposes an actor; see §4.3)
- `Announce(CaseLedgerEntry)` — canonical state replication and broadcast
- `Announce(VulnerabilityCase)` — full case snapshot delivery to a participant
- `Update(VulnerabilityCase)` — case metadata change
- *Source: `specs/case-management.yaml` CM-11, CM-17; `notes/case-communication-model.md`*

### 5.5 Trust and Bootstrap Semantics

- Creator-signed `Create(VulnerabilityCase)` as the trust root
- Late-joiner invite path and trust establishment
- Pre-bootstrap message queuing
- *Source: `specs/case-bootstrap-trust.yaml` (CBT-01–CBT-05)*

### 5.6 Error and Acknowledgement Messages

The formal protocol definition includes acknowledgement (`RK`, `EK`, `CK`) and
error (`RE`, `EE`, `CE`) message types for each state model. Their status in this
specification is **not uniform**, and implementers must not assume symmetry.

| Shorthand | Dispatchable? | Notes |
|---|---|---|
| `RK` | **Yes** | `MessageSemantics.ACK_REPORT`; wire form `Read(Offer(VulnerabilityReport))` |
| `EK`, `CK` | No | No `MessageSemantics` value; no entry in `SEMANTICS_ACTIVITY_PATTERNS` |
| `RE`, `EE`, `CE` | No | No `MessageSemantics` value; no wire representation |

**Error message types are deliberately unmodelled, not merely unimplemented.**
The decision (ADR-0049) is that the protocol core does not model inbound error
message types at all. The reasoning: an implementation cannot *send* these
messages — there is no error-message vocabulary in the core — so a responder for
them would be answering a message class the protocol has no notion of.

The substitute is not a different encoding of the same message. It is a different
mechanism: a participant raises a problem by posting `Add(Note)` targeted at the
case, which the Case Owner sees and may answer with another `Add(Note)`,
propagating back through normal ledger replication. Anything outside that path is
out-of-band and outside the scope of this specification.

Consequences for implementers:

- An implementation MUST NOT expect to receive `RE`, `EE`, `CE`, `EK`, or `CK`
  as dispatchable protocol messages.
- Whether the protocol *should* define a negative-acknowledgement facet is an
  open question, not a settled omission. Currently, unprocessable inbound
  messages are dead-lettered with no sender notification.

- *Source: ADR-0049; `specs/message-semantics-mapping.yaml` MSM-01-007,
  MSM-02-008, MSM-02-009, MSM-03-007; `vultron/core/behaviors/note/`*

### 5.7 Shorthand → Wire Form Mapping

Normative mapping from protocol shorthand through dispatch semantic to AS2 wire
form. Where a wire form is shared by several shorthands, disambiguation is by
local state or object payload as noted.

| Shorthand | `MessageSemantics` | AS2 wire form |
|---|---|---|
| `RS` | `SUBMIT_REPORT` | `Offer(VulnerabilityReport)` |
| `RI` | `INVALIDATE_REPORT` | `TentativeReject(Offer(VulnerabilityReport))` |
| `RV` | `VALIDATE_REPORT` | `Accept(Offer(VulnerabilityReport))` |
| `RD` | `DEFER_CASE` | `Ignore(VulnerabilityCase)` |
| `RA` | `ENGAGE_CASE` | `Join(VulnerabilityCase)` |
| `RC` | `CLOSE_REPORT` | `Reject(Offer(VulnerabilityReport))` |
| `RK` | `ACK_REPORT` | `Read(Offer(VulnerabilityReport))` |
| `EP`, `EV` | `INVITE_TO_EMBARGO_ON_CASE` | `Invite(Event)[context=VulnerabilityCase]` |
| `EA`, `EC` | `ACCEPT_INVITE_TO_EMBARGO_ON_CASE` | `Accept(Invite(Event)[context=VulnerabilityCase])` |
| `ER`, `EJ` | `REJECT_INVITE_TO_EMBARGO_ON_CASE` | `Reject(Invite(Event)[context=VulnerabilityCase])` |
| `ET` | `REMOVE_EMBARGO_EVENT_FROM_CASE` | `Remove(Event)` |
| `CV`–`CA` | `ADD_CASE_STATUS_TO_CASE` | `Add(CaseStatus)[target=VulnerabilityCase]` |
| `RE`, `EE`, `CE`, `EK`, `CK` | *(none — see §5.6)* | *(none)* |

Note the two collision classes: embargo revision shorthands collide with their
initial-proposal counterparts (resolve via local EM state, §5.2), and all six CS
status shorthands collide (resolve via `CaseStatus` payload, §5.3).

- *Source: `specs/message-semantics-mapping.yaml` (MSM-01–MSM-03);
  `specs/vultron-as2-mapping.yaml` (VAM-01–VAM-09);
  `vultron/core/models/events/base.py`*

### 5.8 Knowledge Model and Actor Isolation

- Each actor maintains its own replica of case state
- "Full inline object" rule — no cross-actor references
- What an actor knows vs. what is globally true
- *Source: `specs/actor-knowledge-model.yaml` (AKM-01–AKM-04)*

---

## 6. Behavioral Layer — State Machines [N]

This section specifies five state machines: **RM, EM, VFD, PXA, and PEC**. VFD
and PXA together constitute the CS dimension (§3.2).

!!! note "Note on scope"
    The original Vultron protocol design specified four state machines: RM, EM,
    VFD, and PXA. A fifth — the Participant Embargo Consent (PEC) machine —
    emerged during implementation when it became clear that the case-level EM
    state was insufficient to capture individual participant consent posture.
    PEC is fully normative; implementations that predate this specification
    should treat it as a required addition.

Two conventions apply throughout:

- A participant maintains its own state **and** a model of other participants'
  states. Where a transition rule applies to one and not the other, this is
  stated explicitly (§6.3.4).
- Transitions listed without a named trigger are driven by the corresponding
  protocol message from §5.

### 6.1 Report Management (RM) State Machine

#### 6.1.1 States

- `RM.START`, `RM.RECEIVED`, `RM.INVALID`, `RM.VALID`, `RM.DEFERRED`,
  `RM.ACCEPTED`, `RM.CLOSED`
- *Source: `vultron/core/states/rm.py`; `docs/topics/process_models/rm/`*

#### 6.1.2 Transitions and Guards

- Full transition table with preconditions
- Which messages trigger which transitions
- *Source: `docs/reference/formal_protocol/transitions.md`*

#### 6.1.3 Per-Participant RM Tracking

Each participant tracks its own RM state independently; a participant is the
authority on its own RM state (§4.4.1).

`RM.RECEIVED` is the entry state for a participant joining a case, reached by
several paths:

- **Invited participant** — on `Accept(Invite)`. This records willingness to
  join and, where an embargo is active, consent to it. It does **not** constitute
  validation of the report: the invitee has seen only a case stub at that point.
- **Direct report recipient** — on receiving a report.
- **Case proposal recipient** — on receiving a `CaseProposal`.

The triage cycle (`RECEIVED → VALID | INVALID → ACCEPTED | DEFERRED`) is a
distinct subsequent step that the participant runs **after** the full case
replica has been delivered to it.

!!! note "`Accept(Invite)` does not mean `RM.ACCEPTED`"
    Two different protocol acts are easily conflated: *joining a case* and
    *accepting a report for action*. `Accept(Invite)` is the former. A
    participant cannot accept what it has not seen, and the Case Actor MUST NOT
    treat a participant as having committed to the case until it receives an RM
    status message from that participant confirming the transition.

    See §6.4.7 for why this matters to case delivery.

- *Source: `specs/case-management.yaml` CM-11-001, CM-11-002, CM-11-004,
  CM-17-004; ADR-0051*

### 6.2 Embargo Management (EM) State Machine

#### 6.2.1 States

- `EM.NONE`, `EM.PROPOSED`, `EM.ACTIVE`, `EM.REVISE`, `EM.EXITED`
- This is the **case-level** collective embargo state, distinct from
  per-participant consent (see §6.4)

!!! warning "`NO_EMBARGO` names a state in two different machines"
    `EM.NO_EMBARGO` exists as an alias for `EM.NONE` — the case-level "no embargo
    is in effect". The PEC machine has a *separate* state also named
    `NO_EMBARGO`, meaning "no embargo is in scope **for this participant**"
    (§6.4.1).

    These are different states in different machines, and the machines are
    orthogonal (§6.2.3). A case at `EM.ACTIVE` may hold a participant at
    `PEC.NO_EMBARGO`. Implementations SHOULD prefer `EM.NONE` in code and
    documentation to reduce the collision surface.

- *Source: `vultron/core/states/em.py`; `docs/topics/process_models/em/`*

#### 6.2.2 Transitions and Guards

Triggers are `PROPOSE`, `ACCEPT`, `REJECT`, `TERMINATE`:

| From | Trigger | To |
|---|---|---|
| `NONE` | `PROPOSE` | `PROPOSED` |
| `PROPOSED` | `PROPOSE` | `PROPOSED` (further proposals) |
| `PROPOSED` | `REJECT` | `NONE` |
| `PROPOSED` | `ACCEPT` | `ACTIVE` |
| `ACTIVE` | `PROPOSE` | `REVISE` |
| `REVISE` | `PROPOSE` | `REVISE` |
| `REVISE` | `REJECT` | `ACTIVE` (revision declined; prior terms stand) |
| `REVISE` | `ACCEPT` | `ACTIVE` (revised terms adopted) |
| `ACTIVE` | `TERMINATE` | `EXITED` |
| `REVISE` | `TERMINATE` | `EXITED` |

Note that `REJECT` from `REVISE` returns to `ACTIVE`, not to `NONE` — rejecting a
*revision* does not end the embargo, it leaves the existing terms in force. This
differs from `REJECT` at `PROPOSED`, which returns to `NONE` because no terms
were ever in force.

**Embargo duration selection.** Where multiple embargo proposals are outstanding,
participants SHOULD accept the shortest and propose the remainder as revisions.
This is a SHOULD, and it is one of several admissible policies — an
implementation may instead defer to the Case Owner, or apply its own
organizational policy. This specification does not mandate shortest-wins.

**Tacit acceptance.** Where a receiver has a default embargo policy, a sender
submitting a report without proposing terms constitutes tacit acceptance of the
receiver's default. Tacit acceptance is a property of the *default-policy* path,
not a general substitute for explicit consent: embargo agreement or rejection
SHOULD NOT otherwise be tacit.

- *Source: `vultron/core/states/em.py`;
  `docs/reference/formal_protocol/transitions.md`;
  `specs/embargo-policy.yaml`; `specs/vultron-protocol-spec.yaml` VP-06, VP-07;
  `notes/embargo-default-semantics.md`; `notes/embargo-lifecycle.md`*

#### 6.2.3 Relationship to PEC

- EM tracks whether a case has an active embargo; PEC tracks whether each
  participant has consented to it — these are orthogonal questions
- EM entering `REVISE` triggers a bulk `SIGNATORY → LAPSED` transition in
  all participants' PEC machines
- EM exiting (`EXITED`) triggers `RESET` on all participants' PEC machines
- *Source: `notes/participant-embargo-consent.md`; ADR-0048*

### 6.3 Case State (CS) Dimensions

#### 6.3.1 VFD — Participant-Specific Axis (Vendor/Fix/Deploy)

VFD tracks what a **specific participant** has done. It is monotonic and
strictly ordered: exactly four states, since a fix cannot be deployed before it
is ready, nor ready before the vendor is aware.

| State | Vendor aware | Fix ready | Fix deployed |
|---|---|---|---|
| `vfd` | no | no | no |
| `Vfd` | yes | no | no |
| `VFd` | yes | yes | no |
| `VFD` | yes | yes | yes |

Transition drive authority is governed by §7.4.1.

- *Source: `vultron/core/states/cs.py` (`CS_vfd`);
  `docs/topics/process_models/cs/`*

#### 6.3.2 PXA — Participant-Agnostic Axis (Public/eXploit/Attacks)

PXA tracks the state of the world, not of any participant. Unlike VFD, the three
axes are independent, giving **eight** states: `pxa`, `Pxa`, `pXa`, `pxA`, `PXa`,
`PxA`, `pXA`, `PXA`.

Any participant MAY report PXA observations (§7.4.2).

!!! note "The `pX→PX` invariant: two PXA states are ephemeral"
    Publication of an exploit implies public awareness. `pXa` and `pXA` — exploit
    public while the public is unaware — are therefore transient: they resolve
    immediately to `PXa` and `PXA` respectively.

    Implementations SHOULD treat `pX*` as a state that is passed through rather
    than rested in. Whether this invariant is normatively enforced, and where, is
    currently underspecified (§6.3.3).

- *Source: `vultron/core/states/cs.py` (`CS_pxa`)*

#### 6.3.3 Case State as a Compound Tuple

Case State is the pair `CS = (VFD, PXA)` — 4 × 8 = 32 compound states.

Not all orderings among these are reachable or meaningful, and some sequences
carry normative weight (for example, `CP` must precede `ET` where public
disclosure triggers embargo teardown, §6.5).

!!! warning "Ordering constraints are not yet normatively specified"
    CS ordering constraints are currently described in three non-normative
    places — a code docstring (the `pX→PX` invariant), a *measurement*-oriented
    reference document (possible histories), and a design note — and in no spec
    group. An implementer has no normative statement to conform to.

    Closing this gap is required before conformance claims can meaningfully cover
    CS ordering. Treat the material cited below as informative for now.

- *Source: `docs/topics/process_models/cs/transitions.md`;
  `docs/reference/measuring_cvd/possible_histories.md`;
  `notes/behavioral-conformance-specs.md`*

#### 6.3.4 Receiving CS Messages: Own State vs. Model of Others

A participant maintains its own CS state **and** a model of every other
participant's CS state. These are updated by different events, and conflating
them is a common implementation error:

- Receiving a CS message (`CV`, `CF`, `CD`) updates the receiver's **model of the
  sender's** VFD state. The receiver's own CS state is unchanged. The receiver
  emits `CK` to acknowledge.
- Driving one's *own* VFD transition happens through the local trigger path and
  is subject to the role gating in §7.4.1.
- PXA is shared world-state rather than participant-specific, so an adopted PXA
  observation updates the canonical case status (§6.5.1), not a per-participant
  model.

- *Source: `specs/cs-behavior.yaml` CSB-01 through CSB-04;
  `docs/topics/process_models/model_interactions/_cs_global_local.md`*

### 6.4 Participant Embargo Consent (PEC) State Machine [N]

!!! note "Provenance"
    PEC was not part of the original protocol design. It emerged during
    implementation of the embargo subsystem, when the case-level EM state
    proved unable to distinguish between "no embargo exists" and "this
    participant has not yet consented." It is treated as normative here because
    correct embargo semantics cannot be specified without it.

#### 6.4.1 States

- `NO_EMBARGO` — no embargo in scope for this participant (initial state; also
  the reset destination when an embargo is terminated)
- `INVITED` — participant has received an embargo invitation; response pending
- `SIGNATORY` — participant has accepted current embargo terms
- `LAPSED` — was signatory; case embargo entered `REVISE`; not yet re-accepted
- `DECLINED` — explicitly declined, or timed out without responding (pocket veto)
- *Source: `vultron/core/states/participant_embargo_consent.py`; `notes/participant-embargo-consent.md`*

#### 6.4.2 Transitions and Guards

| From | Trigger | To |
|---|---|---|
| `NO_EMBARGO` | Embargo proposed; participant invited | `INVITED` |
| `NO_EMBARGO` | Direct/implicit/self-determined consent | `SIGNATORY` |
| `NO_EMBARGO` | Refusal without formal invitation | `DECLINED` |
| `INVITED` | Accept | `SIGNATORY` |
| `INVITED` | Reject | `DECLINED` |
| `INVITED` | Timeout (pocket veto) | `DECLINED` |
| `SIGNATORY` | EM enters `REVISE` | `LAPSED` |
| `LAPSED` | Re-invitation extended | `INVITED` |
| `LAPSED` | Accept revised terms | `SIGNATORY` |
| `LAPSED` | Decline revised terms | `DECLINED` |
| `LAPSED` | Timeout (pocket veto) | `DECLINED` |
| `DECLINED` | Case owner re-invites | `INVITED` |
| Any | EM exits (`EXITED`) | `NO_EMBARGO` (RESET) |

Expressed as triggers: `INVITE` accepts `NO_EMBARGO | LAPSED | DECLINED`;
`ACCEPT` and `DECLINE` each accept `NO_EMBARGO | INVITED | LAPSED`; `REVISE`
accepts only `SIGNATORY`; `RESET` accepts any state.

!!! warning "`LAPSED` is not the timeout state"
    `LAPSED` is reached **only** from `SIGNATORY`, and **only** via the `REVISE`
    trigger. It means "prior consent no longer covers the revised terms."

    It is **not** the pocket-veto destination. Both timer paths
    (`INVITED → DECLINED` and `LAPSED → DECLINED`) terminate in `DECLINED`.
    Confusing the two is a known and recurring documentation error.

Neither `LAPSED` nor `DECLINED` is terminal — both can be re-invited.

- *Source: `vultron/core/states/participant_embargo_consent.py`;
  `notes/participant-embargo-consent.md`; `specs/case-management.yaml` CM-18-003,
  CM-18-004; ADR-0048*

#### 6.4.3 Semantics of `NO_EMBARGO`

- `NO_EMBARGO` means **absence of an embargo context**, not "not yet consented"
- Direct `ACCEPT` and `DECLINE` from `NO_EMBARGO` are valid (no invitation
  required) to accommodate self-determined embargoes and implicit reporter consent
- The transition `SIGNATORY → INVITED` MUST be rejected (consent cannot be
  retroactively un-given by re-invitation)
- *Source: ADR-0048; `notes/participant-embargo-consent.md`*

#### 6.4.4 Pocket Veto and RSVP Deadlines (Timer-Based Transitions)

- `INVITED → DECLINED` and `LAPSED → DECLINED` are timer-based
- An `Invite(EmbargoEvent)` MAY carry an activity-level `end_time` giving an
  explicit RSVP-by deadline. When present it is authoritative; when absent the
  configurable policy window applies (default 7 days). The pocket veto is the
  implicit form of the same mechanism, not a second one
- `Invite.end_time` (RSVP-by) MUST NOT be confused with
  `Invite.object_.end_time` (embargo expiry) — the same invitation carries both
- A minimum RSVP window (default 72h) MUST be enforced; a receiver getting a
  sub-minimum deadline MUST clamp it up rather than reject the invitation
- Enforcement authority is the CaseActor (`CVDRole.CASE_MANAGER`), evaluated
  lazily from `(end_time, now)`; no scheduler is required
- A lapse records `DECLINED` — the same state as an explicit refusal. The
  distinction is provenance, carried by the canonical ledger, not by a
  dedicated PEC state
- A late `Accept` MUST NOT be refused on deadline grounds: honour it if the
  terms are current, re-invite with current terms if they are stale, or
  acknowledge as a no-op (retaining case participation) if no embargo remains
- *Source: `notes/participant-embargo-consent.md` §"Pocket Veto" and
  §"RSVP Deadlines on Embargo Invites"; ADR-0059; CM-18-002, CM-27, EP-07,
  EMB-17*

#### 6.4.5 Embargo Meta-Protocol Delivery to Non-Signatories

- Embargo meta-protocol messages — `Invite(Event)`, `Accept`/`Reject` thereof,
  and `Remove(Event)` — MUST be delivered even to `DECLINED` and `LAPSED`
  participants. A participant cannot be re-invited to revised terms it never
  learns about.
- Only case **content** (report details, fix status, sensitive notes) is gated on
  `SIGNATORY` status (§6.4.7).
- *Source: `notes/participant-embargo-consent.md`*

#### 6.4.6 Relationship to `embargo_adherence`

`embargo_adherence` is the boolean projection of PEC state: `True` iff
PEC = `SIGNATORY`, `False` otherwise.

The implementation MUST expose `embargo_adherence` as a computed property
(e.g., Pydantic `@computed_field`) derived from `consent.state`. It MUST NOT
be a stored field that can drift from the PEC state it projects.
Consent changes MUST be applied as a PEC trigger through the validated
transition path (ADR-0048, ADR-0056).

- *Source: `specs/case-management.yaml` CM-18-008; ADR-0056*

#### 6.4.7 Gating Full Case Delivery

Before the Case Actor delivers full case content
(`Announce(VulnerabilityCase)` carrying report details, vulnerability
description, and sensitive notes), **both** conditions MUST hold for the
recipient:

1. The participant is **admitted to the case** — RM state is at least
   `RM.RECEIVED`.
2. The participant is a **signatory to the active embargo**
   (`embargo_adherence = True`), **OR** there is no active embargo
   (`EM.NONE`).

!!! warning "The gate is admission plus consent — not completed triage"
    It is tempting to read condition 1 as `RM.ACCEPTED`. That reading is wrong
    and self-defeating: an invitee is recorded at `RM.RECEIVED` on
    `Accept(Invite)`, and reaches `ACCEPTED` only *after* receiving the full case
    and running its triage cycle (§6.1.3). Requiring `ACCEPTED` before delivery
    would mean a participant could never obtain the case it needs in order to
    reach the state that gates it.

    **Embargo consent — not RM progress — is the substantive gate on case
    content.** The ordering is: admit the participant at `RM.RECEIVED`, resolve
    embargo consent, then deliver the full case.

Note the consequence for §6.5's cascade ordering: `Accept(Invite)` implies consent
to any active embargo, which is what allows delivery to proceed immediately rather
than waiting on a separate consent round-trip.

- *Source: `specs/message-validation.yaml` MV-10-005, MV-10-006;
  `specs/case-management.yaml` CM-10-004, CM-11-001, CM-17-004, CM-18-005*

### 6.5 Model Interactions and Cascade Rules

State transitions in one dimension trigger obligations in others. Cascades are
event-driven: a state change produces a domain event, which the Case Actor
handles. Each cascade step is independently authorizable, and ordering between
steps is normative where noted.

Key cascades:

- **Invitation accepted → admit, resolve consent, deliver**: on `Accept(Invite)`
  the Case Actor MUST, in order, (a) commit a ledger entry and fan it out,
  (b) create the participant record at `RM.RECEIVED`, (c) sign embargo consent if
  an embargo is active, (d) send `Announce(VulnerabilityCase)` with the full
  snapshot, and (e) backfill prior ledger entries in log-index order. The
  ordering of (b)–(d) is load-bearing (§6.4.7).
- **EM enters `REVISE` → bulk PEC lapse**: all participants currently at PEC
  `SIGNATORY` MUST be transitioned to `LAPSED`.
- **EM exits → PEC reset**: all participants' PEC machines MUST be reset to
  `NO_EMBARGO`.
- **PXA observation adopted → embargo teardown**: canonical adoption of any
  status carrying `CS.P`, `CS.X`, or `CS.A` MUST trigger embargo teardown
  evaluation (§6.5.1, Seam 2).
- **Embargo teardown → state replication**: termination of an active embargo
  SHOULD produce a fresh `Announce(CaseLedgerEntry)` to all participants.

#### 6.5.1 Status Adoption: The Two-Seam Model

A reported status becomes canonical case state through two independent
authorization seams. This structure exists because "record what a participant
claimed" and "act on that claim as truth" are separate decisions with separate
authority.

**Seam 1 — Adoption.** A participant reports an observation via
`Add(ParticipantStatus)`. The receiving Case Actor records the claim, then
decides whether to treat it as canonical:

- A Case Owner's report MUST be adopted without requiring approval — requiring
  the Case Owner to approve its own report would be circular (§7.4.4).
- All other senders pass through a configurable approval gate. The default
  policy is to auto-adopt.
- On adoption, the Case Actor emits a self-addressed `Add(CaseStatus)` to itself
  acting as Case Manager, which performs the canonical write.
- The tree that records the claim MUST NOT execute side-effects directly.

**Seam 2 — Side-effects.** After the canonical write, the Case Actor evaluates
side-effects:

- It MUST check whether the canonical status carries `CS.P`, `CS.X`, or `CS.A`.
- If any is present, it MUST initiate embargo teardown.
- **This check MUST run after the canonical write, never before.**
- A second configurable gate MAY require approval before executing teardown;
  the default is to proceed.

The seams are deliberately independent: the adoption decision knows nothing about
teardown, and the side-effects decision cannot tell whether the canonical write
originated in an external message or an internal self-emit. That independence is
what lets either be re-policied without touching the other.

!!! note "Where the seam model applies"
    Seam 1 governs *any* reported status, but its authorization question is most
    consequential for participant-agnostic (PXA) observations, where any
    participant may report (§7.4.2) — including reports about *other*
    participants. The default auto-adopt policy means an unapproved third-party
    assertion becomes canonical unless an implementation configures otherwise.

- *Source: `specs/received-status-handling.yaml` RSH-01-001 through RSH-03;
  ADR-0046; `notes/received-status-authorization.md`;
  `notes/protocol-event-cascades.md`; `specs/event-driven-control-flow.yaml`*

### 6.6 Participant Lifecycle Within a Case

- Invitation, acceptance, role assignment, removal
- Case ownership and transfer
- *Source: `specs/case-management.yaml`; `notes/ownership-transfer.md`*

---

## 7. Conformance [N]

### 7.1 Conformance Model Overview

Conformance is two-dimensional: a **capability tier** (what protocol machinery an
implementation provides) and a **role profile** (which roles it claims). A
conformance claim takes the form:

> `T{n} / Role [+ Role ...]`

Examples: `T1 / Reporter`, `T1 / Vendor`, `T1 / Vendor + Deployer`,
`T2 / Coordinator + CNA`, `T2 / Coordinator + Case Owner`.

Capability tiers are cumulative: T2 implies T1.
Role obligations are additive and orthogonal: no role subsumes another.

!!! warning "Tiers are not the same as conformance test layers"
    This project uses two distinct numbered schemes, and they must not be
    conflated:

    - **Capability tiers (T0–T2)**, defined here, describe *what an
      implementation provides* — a claim an implementer makes about their
      software.
    - **Conformance test layers (L1–L4)**, used in the behavioral conformance
      material, describe *what a test verifies* — syntax, semantics, behavior,
      and internal process structure. These are orthogonal to tiers: a `T1`
      implementation is tested at layers L1 through L3.

    "T" was chosen over reusing "L" precisely to keep these separable. Earlier
    drafts of this document used `L0`/`L1`/`L2` for tiers; those labels are
    superseded.

### 7.2 Capability Tiers

!!! note "What 'implement a state machine' means"
    Implementing a state machine has two components:

    1. **Track**: maintain a local instance of the machine and update it when
       relevant protocol messages are received from other participants.
    2. **Drive**: send the appropriate protocol messages when *this participant's
       own* state transitions occur (per the "Avoid Surprise" principle).

    Every participant must both track and drive the machines relevant to their
    role. Tracking without driving means other participants are surprised by your
    state changes. Driving without tracking means you are unaware of the case
    state you are acting on.

#### T0 — Consumer

- MUST be able to receive and parse all Vultron message types
- No state machine tracking required; no send obligations
- The minimum for a monitoring, archival, or display tool that reads case
  traffic without participating in coordination

!!! note "T0 is not case participation"
    A T0 implementation can consume messages but cannot be a case Participant: it
    holds no `CaseParticipant` record, has no RM state, and no case is obliged to
    deliver anything to it. An actor that accepts a case invitation has
    implicitly committed to T1 behavior — from that point it must track state and
    notify others of its own transitions.

    T0 is therefore a claim about *software capability*, not a way to sit inside
    a case passively. See §7.3.3 on why "Observer" is not a T0 concept.

#### T1 — Participant

Meaningful case participation requires all five state machines. An
implementation that tracks RM but ignores EM cannot correctly gate its own
embargo behavior; one that ignores CS cannot correctly evaluate disclosure
timing. The machines are not independent add-ons — they are the protocol.

- MUST implement all five state machines: **RM, EM, PEC, VFD, PXA**
  (track and drive, per the definition above)
- MUST send the messages appropriate to its claimed roles when its own state
  transitions occur
- MUST receive and update local state when notified of other participants'
  transitions
- MUST participate in embargo negotiation as appropriate to role: responding to
  `Invite(Event)`, and recording consent or refusal via PEC
- MUST route all case-scoped messages through the Case Actor (§4.4.2)
- Role-specific drive obligations are governed by §7.4

!!! note "Role-specific drive obligations"
    All T1 participants **track** all five machines. Which transitions a
    participant **drives** depends on its role: a Vendor drives its own VFD
    transitions; a Reporter drives RM; any participant may report PXA
    observations. See §7.3 and §7.4.

- *Source: `specs/vultron-protocol-spec.yaml`; `specs/state-machine.yaml`;
  `specs/embargo-policy.yaml`; `specs/case-management.yaml` CM-18*

#### T2 — Coordinator

A T2 implementation provides multi-party case management on behalf of other
participants. This is coordination *authority* — not an additional state machine
requirement, since all five are already required at T1.

- All T1 requirements, plus:
- MUST act as or host a **Case Actor**, and therefore MUST implement the
  single-writer authority rules of §4.4.1
- MUST maintain the authoritative canonical case ledger and replicate it to
  participants via `Announce(CaseLedgerEntry)`
- MUST implement multi-party case management: participant invitation,
  acceptance, role assignment, and case ownership operations
- MUST implement the two-seam status adoption model (§6.5.1), including the
  canonical-write-before-side-effects ordering
- MUST deliver full case content only when the §6.4.7 gate is satisfied

!!! note "Ledger replication scope"
    Whether the full ledger replication protocol belongs in this specification or
    in a companion document is unresolved (see Open Questions). The T2
    requirement above is stable regardless: a Case Actor host must replicate the
    ledger. What may move is the *detailed* replication mechanics — ordering,
    hash-chaining, gap recovery — not the obligation.

- *Source: `specs/sync-ledger-replication.yaml`; `specs/case-management.yaml`;
  `specs/received-status-handling.yaml`; `specs/vultron-protocol-spec.yaml` VP-17-001*

### 7.3 Role Taxonomy

#### 7.3.1 Process Roles

Process roles define what an actor *does* within a case and which protocol
transitions it is authorized to drive. An actor may hold multiple process roles.

| Role | Protocol capability |
|---|---|
| Reporter | Initiates cases; drives `RS`; authoritative source of the original report |
| Vendor | Drives its own VFD transition `f→F` (fix ready, `CF`) |
| Deployer | Drives its own VFD transition `d→D` (fix deployed, `CD`) |
| Coordinator | Drives case participant management; coordinates multi-party disclosure |
| CNA | May directly assign CVE IDs; a non-CNA delegates to an external CNA service. Orthogonal to other roles — typically co-held with Coordinator or Vendor |
| Observer † | Holds no drive obligations for VFD; may report PXA observations (§7.4.2) |

!!! note "† Observer: decided (ADR-0057); Finder: still provisional"
    **Observer** (`CVDRole.OBSERVER`): the rename from `CVDRole.OTHER` is decided
    (ADR-0057). The implementation task (renaming the enum value and all
    references) is tracked in a separate issue. Observer semantics are now
    normative: full participant (CM-25-001), standard Invite/Accept admission
    (CM-25-002), full case content (CM-25-003), RM triage with engagement
    semantics (CM-25-004), VFD exclusion for sole-Observer participants (CM-25-005).
    Role-stacking union principle: CM-26-001.

    **Finder** still requires an ADR before the removal can be treated as normative.
    The formal protocol definition this document builds on (§3.1, §3.4) defines
    the process count over Finders, Vendors, Coordinators, Deployers, and Others.
    `CVDRole.FINDER` exists in the current implementation and is retained until
    the ADR is written.

!!! note "Note on Reporter"
    Reporters are most often also the discoverer of the vulnerability, but
    the protocol is concerned with who reported it, not who found it. The
    identity of the original discoverer may be recorded in the report itself
    or in case Notes, but nothing in the technical protocol hinges on that
    distinction. Reporter is the protocol-salient role from first contact.

#### 7.3.2 Protocol Coordination Roles (protocol authority)

These roles confer specific protocol-layer authority and are distinct from
process roles. They describe what an actor *controls* within the protocol
machinery, not what it does in the world.

| Role | Protocol authority |
|---|---|
| Case Owner | Authoritative decision-maker for a case; status updates are treated as authoritative without requiring approval; drives shared EM transitions |
| Case Manager | AS actor performing case replica synchronization and case management on behalf of the case owner; always co-held with Coordinator |

**Delegation scenarios**: Protocol responsibilities may transfer during a case
lifecycle. For example, a Reporter who initially creates a case may delegate
coordination to a Coordinator (reporter → coordinator hand-off), or a primary
Vendor may bring in additional Vendors as the case grows. When a Case Owner
transfers ownership (via `Offer(VulnerabilityCase)` / `Accept` handshake routed
through the Case Actor), the receiving actor acquires Case Owner authority and
the associated protocol responsibilities.

!!! note "Open architectural question: Case Actor identity during ownership transfer"
    Because the Case Actor's URI is the identity anchor for the canonical ledger,
    transferring Case Actor ownership raises a re-keying question: future
    cryptographic identity and case encryption designs make re-keying undesirable.
    The design for ownership transfer across cryptographic boundaries requires
    further work before this aspect can be normative.

#### 7.3.3 Roles and Tiers Are Independent

A role is a position within a case. A tier is a property of software. Mixing them
produces contradictions, so the relationship is stated explicitly:

- Every case Participant — whatever its roles — is at minimum **T1**. Holding a
  role means having a `CaseParticipant` record, an RM state, and therefore
  tracking obligations.
- **T0 is not a role.** A T0 implementation consumes messages without
  participating; it holds no role and no case owes it delivery.
- A T2 implementation additionally hosts the Case Actor. T2 is commonly co-held
  with Coordinator and Case Manager, but the tier is what obliges ledger
  authority, not the role name.

!!! warning "Observer is a participant role, not a passive tier"
    An Observer that is *in a case* is a T1 participant: it has an RM state, it is
    subject to embargo consent, and it may report PXA observations. It is
    distinguished by holding no VFD drive obligations — not by being exempt from
    tracking.

    How a role-light participant is admitted to a case, and what content it
    receives, is not fully specified. Presumably admission is by invitation from a
    Case Owner or Case Manager, on the same `Invite` / `Accept(Invite)` path as
    any other participant — but the invitation flow for a participant with no
    functional role has not been worked through. See Open Questions.

### 7.4 Role-Specific Normative Requirements

#### 7.4.1 Participant-Specific CS Transitions (VFD)

VFD records what a specific participant has done, so drive authority is scoped to
the participant that did it.

For **self-reported** VFD transitions (a participant advancing its own state via
the local trigger path):

- `f→F` (`VFd`, fix ready): MUST only be driven by an actor holding Vendor;
  MUST fail when Vendor is absent
- `d→D` (`VFD`, fix deployed): MUST only be driven by an actor holding Deployer;
  MUST fail when Deployer is absent
- A Vendor-only actor MUST NOT advance past `VFd` without also holding Deployer

!!! warning "Do not conflate `P` (public aware) with `D` (fix deployed)"
    A publication notification MUST set only the PXA public-awareness state. It
    MUST NOT imply fix deployment. `P` is participant-agnostic world state; `D` is
    a participant-specific act requiring the Deployer role. An implementation that
    treats "we published" as "it's deployed" produces an unauthorized VFD
    advance.

!!! note "`v→V` (vendor awareness) has no specified drive path"
    The gating above covers `f→F` and `d→D` only. The first VFD transition —
    `v→V`, vendor becomes aware — has **no trigger-side specification and no
    implementation**, and its design intent differs from the others: `CV` was
    conceived as a *third-party assertion* ("I delivered a report to this
    Vendor"), not a vendor self-report. Who may assert it, whether the vendor may
    dispute it, and whether transport-level delivery success suffices are all
    open. Tracked as a Concern; do not infer a rule from this document's silence.

- *Source: `specs/cs-behavior.yaml` CSB-15-001, CSB-15-002, CSB-15-003;
  receive-side counterparts CSB-01 through CSB-04 (§6.3.4)*

#### 7.4.2 Participant-Agnostic CS Transitions (PXA)

PXA records the state of the world rather than of any participant, so **any**
participant MAY report a PXA observation. These transitions are role-ungated:
information may become public, exploits may appear, and attacks may be observed
independently of anything a case participant does or causes.

- `p→P` (publicly aware): any participant may report
- `x→X` (exploit public): any participant may report
- `a→A` (attacks observed): any participant may report

Reporting is not adoption. A reported observation is a claim; whether it becomes
canonical case state, and whether it triggers embargo teardown, is decided by the
two-seam model in **§6.5.1**. The role rule here — *who may report* — is
deliberately separate from the authorization rules there — *what the Case Actor
does with a report*.

!!! note "Informative: the sentinel pattern"
    A participant that monitors external sources (threat feeds, public
    disclosures, vulnerability databases) and reports what it finds into a case is
    referred to as a **sentinel**. This is the anticipated mechanism for PXA
    observations originating outside the case.

    The sentinel is currently a *design pattern* rather than a specified protocol
    role: no spec group defines a sentinel's trust relationship to a case, and
    nothing distinguishes a sentinel's observations from any other participant's.
    Given that Seam 1's default policy is to auto-adopt non-owner reports, an
    unspecified external reporter is a trust-model question and not merely a
    naming one. Treat this note as informative.

- *Source: `specs/cs-behavior.yaml`; ADR-0047 (sentinel pattern);
  §6.5.1 for adoption authorization*

#### 7.4.3 CVE ID Assignment

An actor holding CNA MAY directly assign CVE IDs when eligibility criteria
are met (scope, product coverage, assignability checks per CNA Operational
Rules). An actor not holding CNA MUST delegate ID assignment to an external
CNA service.

- *Source: `vultron/core/behaviors/report/assign_cve_id_tree.py`*

#### 7.4.4 Case Owner Authority

A Case Owner's status updates MUST be accepted without requiring approval from
a case management policy engine. Requiring a Case Owner to approve their own
updates would be circular.

For all other senders, implementations MAY require approval via a configurable
policy gate before adopting a reported status update.

- *Source: `notes/received-status-authorization.md`; `specs/case-management.yaml`*

### 7.5 Conformance Testing Approach

- Observable behavior is the test basis — not implementation internals
- Test cases are expressed as message-sequence scenarios with expected state
  outcomes
- Functional capabilities (develop fix, deploy fix, publish advisory) are
  role-defining but not directly protocol-observable; conformance is verified
  through the protocol messages they produce, not the work behind them

Conformance testing is organized in four **layers**, which describe what a test
verifies. These are orthogonal to the capability tiers of §7.2 (see the warning
in §7.1):

| Layer | Verifies |
|---|---|
| L1 — Syntax | Messages are well-formed against the wire format (§4) |
| L2 — Semantics | Each message drives the correct state transition (§5, §6) |
| L3 — Behavior | Correct observable outputs: right messages emitted and states reached, given input state plus received message |
| L4 — Process | Correct internal decision structure (e.g. precondition before state write before side-effect) |

L4 is only enforceable against a reference implementation and is therefore
outside the scope of independent conformance claims. Some process ordering
surfaces at L3 where the output sequence is itself observable — the
canonical-write-before-side-effects rule of §6.5.1 being the clearest case.

- *Source: `notes/behavioral-conformance-specs.md`;
  `specs/rm-behavior.yaml`, `specs/em-behavior.yaml`, `specs/cs-behavior.yaml`*

---

## 8. Security Considerations [N/I]

### 8.1 Trust Model

- Actor identity and verification
- Case bootstrap as the trust establishment mechanism

### 8.2 Embargo Integrity

- Preventing premature disclosure through protocol adherence
- What happens when an actor defects from an active embargo

### 8.3 Replay and Idempotency

- Message deduplication requirements
- *Source: `specs/idempotency.yaml`*

### 8.4 Confidentiality

- What is normatively in-scope for encryption (deferred in prototype)
- *Source: `specs/encryption.yaml`*

---

## 9. IANA / Namespace Considerations [I]

- Vultron vocabulary namespace registration (future)
- AS2 extension type naming conventions

---

## 10. Informative Annexes

### Annex A — Worked Example: Single-Vendor CVD [I]

- *Source: `docs/howto/worked_example.md`*

### Annex B — Worked Example: Multi-Party CVD [I]

- Examples should be derived directly from current demo scripts, not older
  design documents — the implementation is authoritative at this stage
- *Source: `vultron/demo/scenario/fv_demo.py` (Reporter-Vendor);
  `vultron/demo/scenario/fcv_demo.py` (Reporter-Coordinator-Vendor);
  `vultron/demo/scenario/fvcv_handoff_demo.py` (coordinator hand-off);
  `vultron/demo/scenario/README.md` for the full scenario inventory*

### Annex C — Notation Reference [I]

- *Source: `docs/reference/notation.md`*

### Annex D — Possible Case Histories [I]

- Ordering constraints on CS state transitions (see §6.3.3 — these are not yet
  normatively specified)
- *Source: `docs/reference/measuring_cvd/possible_histories.md`;
  `docs/topics/process_models/cs/transitions.md`*

### Annex E — Relationship to ActivityPub [I]

- Where Vultron follows ActivityPub and where it diverges
- *Source: `notes/activitystreams-semantics.md`*

### Annex F — Behavior Tree Reference Implementation [I]

- BTs are one valid implementation pattern, not normative — the spec does not
  require a BT implementation; BTs are used in the reference implementation
- **Implementation is authoritative**: at this stage, `vultron/core/behaviors/`
  is the ground truth for BT structure. Documentation in
  `docs/topics/behavior_logic/` should be verified against the implementation
  before treating it as normative for the spec
- *Source: `vultron/core/behaviors/` (authoritative); `docs/topics/behavior_logic/`
  (narrative reference, verify against implementation)*

---

## Open Questions (to resolve before circulating)

1. **Namespace URI** — Is there a stable `vultron:` or `https://vultron.example/`
   namespace ready to cite?
2. **Sync/replication** — Is the ledger replication protocol in scope for this
   RFC, or a separate companion spec? The T2 obligation to replicate is stable
   either way (§7.2); what may move is the detailed mechanics.
3. ~~**ActivityPub vs. bare AS2**~~ — Resolved for this version. §4.1 states the
   current normative floor as AS2 vocabulary only, with an informative note that
   a future version is expected to require full ActivityPub conformance at T1+.
   Tracked in issue #2068.
4. **Background material depth** — How much CVD domain background belongs here
   vs. a companion "CVD Concepts" document?
5. **Finder removal ADR** — Decision to drop the Finder role needs an ADR before
   the spec circulates. Rationale: Reporter is the protocol-salient role; Finder
   identity may be recorded in the report or case Notes but has no protocol effect.
   Note the reach: `docs/reference/formal_protocol/index.md` defines the process
   count $N$ over Finders, Vendors, Coordinators, Deployers, and Others, and §3.1
   and §3.4 build on that definition. Marked provisional in §7.3.1.
6. ~~**Observer rename ADR**~~ — Resolved. ADR-0057
   (`docs/adr/0057-observer-participant-role.md`) decided the rename and Observer
   semantics (CM-25, CM-26). Implementation (code rename) tracked separately.
7. ~~**PXA adoption policy**~~ — Resolved. Two-seam model specified in §6.5.1:
   Seam 1 (adoption) and Seam 2 (side-effects), with the
   canonical-write-before-side-effects ordering normative. Source:
   `specs/received-status-handling.yaml`, `notes/received-status-authorization.md`,
   ADR-0046.
8. ~~**Observer admission and content scope**~~ — Resolved by ADR-0057 and CM-25.
   Standard Invite/Accept admission (CM-25-002), full case content via MV-10-005
   gate (CM-25-003), RM triage with engagement semantics (CM-25-004). Related to
   #6 (now also resolved).
9. **CNA eligibility criteria** — The CVE ID assignment tree encodes CNA
   Operational Rules v4.1.0 criteria inline. Should the RFC cite these as
   normative external requirements, or treat the eligibility checks as
   implementation-defined?
10. ~~**Capability tier structure**~~ — Resolved (consolidates the former items
    10–13). All five state machines (RM, EM, PEC, VFD, PXA) are required at T1;
    the machines are not independent add-ons. T0 = consumer (parse only, not a
    Participant); T1 = Participant (all machines, role-appropriate drive
    obligations); T2 = Coordinator (Case Actor hosting, ledger replication, and
    multi-party case management as one inseparable coordination-authority tier).
    Tiers were renamed from `L{n}` to `T{n}` to avoid collision with the L1–L4
    conformance *test layers* (§7.1, §7.5).
11. ~~**Ledger-based status broadcast**~~ — Resolved. `Announce(CaseStatus)` does
    not exist: there is no such `MessageSemantics` value, and
    `Announce(CaseLedgerEntry)` is the only mechanism by which participants learn
    of accepted case-state changes. All references have been corrected.
12. **CS ordering constraints are unspecified** — §6.3.3. Ordering rules
    (including the `pX→PX` invariant and `CP`-before-`ET`) exist only in a code
    docstring, a measurement-oriented reference document, and a design note — no
    spec group. Conformance claims cannot cover CS ordering until this is closed.
13. **`v→V` drive authority** — §7.4.1. The first VFD transition has no
    trigger-side specification and no implementation. Design intent is a
    third-party assertion ("I notified this Vendor"), which raises questions about
    who may assert, whether the subject may dispute, and whether transport-level
    delivery success suffices. Filed as a Concern.
14. **`embargo_adherence` derived vs. stored** — §6.4.6. Resolved by ADR-0056:
    `embargo_adherence` is a computed property derived from PEC state.
    Implementation issue tracked separately.
15. **Negative acknowledgement** — §5.6. Error message types are deliberately
    unmodelled (ADR-0049), and unprocessable inbound messages are dead-lettered
    with no sender notification. Whether the protocol needs an error-reply facet
    is open.
16. **Sentinel as a specified role** — §7.4.2. Currently a design pattern with no
    spec group defining its trust relationship to a case. Given Seam 1's
    auto-adopt default, this is a trust-model question.
