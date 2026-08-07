---
title: "Draft: Vultron Protocol Specification"
version: "2026.08.07.17.06"
status: draft
description: >
  Working draft outline of the Vultron Protocol specification, organized as
  an RFC-like document. Not yet ready for external circulation. Sections
  marked [N] are normative; [I] are informative. Source pointers indicate
  the strongest existing material for each section.
---

# Draft: Vultron Protocol Specification

!!! warning "Working Draft"
    This document is a working draft outline. It is not yet ready for external
    circulation. Content is incomplete; source pointers indicate where material
    will be drawn from. Open questions are listed at the end.

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
- *Source: `docs/about/`, ADRs*

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
- *Source: glossary / `docs/_acronyms/`, `vultron/enums/roles.py` (CVDRole)*

### 2.2 Protocol Terms

- Message, Activity, Object, Channel
- State, Transition, Event
- Embargo, Publication
- *Source: `docs/reference/formal_protocol/index.md`*

---

## 3. Protocol Overview [I]

### 3.1 The Protocol as a Communicating Hierarchical State Machine

- Brand & Zafiropulo formal definition
- N processes, disjoint state sets, message sets, successor function
- Global state as (S, C) pair
- *Source: `docs/reference/formal_protocol/index.md` (already written, near-verbatim)*

### 3.2 Tracking Dimensions

The protocol tracks coordination state across four dimensions, each
implemented as a state machine:

- Report Management (RM): lifecycle of a report from receipt to closure
- Embargo Management (EM): negotiated disclosure timing (case-level)
- Case State (CS): multi-dimensional public knowledge state (VFD × PXA)
- Participant Embargo Consent (PEC): per-participant embargo consent posture

RM, EM, and CS were present in the original protocol design. PEC emerged
during implementation (see §6.4) and is fully normative.

- *Source: `docs/topics/process_models/`*

### 3.3 How the Dimensions Interact

- RM drives case progression; EM gates publication; CS reflects observable reality
- State transitions in one dimension can trigger obligations in others
- *Source: `docs/topics/process_models/model_interactions/`, `notes/protocol-event-cascades.md`*

### 3.4 Participants and Roles

- Roles are not exclusive; a participant may hold multiple roles
- N = |Participants|, not |Roles|
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
    floor to ActivityPub at L1 and above. Implementations built against the
    current AS2-only baseline should anticipate that re-evaluation against a
    future ActivityPub-baseline version will be required. The AS2-only profile
    may become a compatibility profile at that point. (See issue #2068.)

- *Source: `specs/vultron-as2-mapping.yaml` (VAM-01 through VAM-09)*

### 4.2 Object Types

- `VulnerabilityCase` — the shared coordination object
- `VulnerabilityReport` — the initial report artifact
- `CaseParticipant` — actor-in-role within a case
- `EmbargoEvent` — embargo proposal/acceptance/revision/termination records
- `CaseStatus` / `ParticipantStatus` — status snapshots
- *Source: `vultron/wire/as2/vocab/objects/`, `specs/vocabulary-model.yaml`*

### 4.3 Activity Types and Canonical Message Forms

- `Create`, `Offer`, `Accept`, `Reject`, `Announce`, `Update` as base verbs
- Vultron-specific nested-object patterns (e.g., `Accept(Offer(EmbargoProposal))`)
- Mapping table: protocol shorthand → AS2 activity type + object type
- *Source: `specs/vultron-as2-mapping.yaml`; `specs/message-semantics-mapping.yaml`*

### 4.4 Addressing and Channels

- Actor URIs as process identifiers
- Point-to-point vs. broadcast semantics
- Inbox/outbox as the delivery model
- *Source: `specs/outbox.yaml` (OX-01–OX-08); `notes/peer-broadcast-failure-semantics.md`*

### 4.5 Serialization

- JSON-LD as the normative serialization
- Required context declarations
- *Source: AS2/ActivityPub standards; `specs/message-validation.yaml`*

---

## 5. Semantic Layer — Message Meanings [N]

### 5.1 Report Management Messages

- RS — Report Submitted
- RI — Report Invalid
- RV — Report Valid
- RD — Report Deferred
- RA — Report Accepted (into a case)
- RC — Report Closed
- RE — Report Embargo (internal, no AS2 dispatch)
- Mapping to RM state transitions
- *Source: `specs/vultron-protocol-spec.yaml`; `specs/message-semantics-mapping.yaml`*

### 5.2 Embargo Management Messages

- EP — Embargo Proposed
- ER — Embargo Revised (counter-proposal)
- EA — Embargo Accepted
- EJ — Embargo Rejected
- ET — Embargo Terminated
- EE, EK — internal/no dispatch variants
- Tacit acceptance semantics
- *Source: `specs/embargo-policy.yaml`; `notes/embargo-lifecycle.md`; `notes/embargo-default-semantics.md`*

### 5.3 Case State Messages

- CV — Vendor Aware
- CF — Fix Ready
- CD — Fix Deployed
- CP — Publicly Aware
- CX — Exploit Public
- CA — Attacks Observed
- CE, CK — internal/no dispatch variants
- *Source: `specs/vultron-protocol-spec.yaml`; `specs/message-semantics-mapping.yaml`*

### 5.4 Case Coordination Messages

- `Create(VulnerabilityCase)` — case initiation
- `Offer(CaseParticipant)` / `Accept(Offer(...))` / `Reject(Offer(...))` — invitation lifecycle
- `Announce(CaseStatus)` — broadcast status update
- `Update(VulnerabilityCase)` — case metadata change
- *Source: `specs/case-management.yaml`; `notes/case-communication-model.md`*

### 5.5 Trust and Bootstrap Semantics

- Creator-signed `Create(VulnerabilityCase)` as the trust root
- Late-joiner invite path and trust establishment
- Pre-bootstrap message queuing
- *Source: `specs/case-bootstrap-trust.yaml` (CBT-01–CBT-05)*

### 5.6 Knowledge Model and Actor Isolation

- Each actor maintains its own replica of case state
- "Full inline object" rule — no cross-actor references
- What an actor knows vs. what is globally true
- *Source: `specs/actor-knowledge-model.yaml` (AKM-01–AKM-04)*

---

## 6. Behavioral Layer — State Machines [N]

!!! note "Note on scope"
    The original Vultron protocol design specified four state machines: RM, EM,
    VFD, and PXA. A fifth — the Participant Embargo Consent (PEC) machine —
    emerged during implementation when it became clear that the case-level EM
    state was insufficient to capture individual participant consent posture.
    PEC is fully normative; implementations that predate this specification
    should treat it as a required addition.

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

- Each participant tracks its own RM state independently
- `RM.RECEIVED` entered only on `Accept(Invite)` for non-originators
- *Source: `specs/case-management.yaml` CM-11; ISSUE-2017*

### 6.2 Embargo Management (EM) State Machine

#### 6.2.1 States

- `EM.NONE`, `EM.PROPOSED`, `EM.ACTIVE`, `EM.REVISE`, `EM.EXITED`
- This is the **case-level** collective embargo state, distinct from
  per-participant consent (see §6.4)
- *Source: `vultron/core/states/em.py`; `docs/topics/process_models/em/`*

#### 6.2.2 Transitions and Guards

- Proposal, counter-proposal, acceptance, rejection, termination paths
- Shortest-embargo-wins rule at case creation
- Tacit acceptance window and semantics
- *Source: `docs/reference/formal_protocol/transitions.md`; `specs/embargo-policy.yaml`*

#### 6.2.3 Relationship to PEC

- EM tracks whether a case has an active embargo; PEC tracks whether each
  participant has consented to it — these are orthogonal questions
- EM entering `REVISE` triggers a bulk `SIGNATORY → LAPSED` transition in
  all participants' PEC machines
- EM exiting (`EXITED`) triggers `RESET` on all participants' PEC machines
- *Source: `notes/participant-embargo-consent.md`; ADR-0048*

### 6.3 Case State (CS) Dimensions

#### 6.3.1 VFD — Participant-Specific Axis (Vendor/Fix/Deploy)

- `VFD` states: `vfd`, `Vfd`, `VFd`, `VFD`
- Vendor aware, fix ready, fix deployed
- Transitions are gated by role (see §7.4.1)
- *Source: `vultron/core/states/cs.py`; `docs/topics/process_models/cs/`*

#### 6.3.2 PXA — Participant-Agnostic Axis (Public/eXploit/Attacks)

- `PXA` states: `pxa`, `Pxa`, `pXa`, `pxA`, etc.
- Public aware, exploit public, attacks observed
- Transitions are ungated — any participant may report world-state observations
  (see §7.4.2)
- *Source: `vultron/core/states/cs.py`*

#### 6.3.3 Case State as a Compound Tuple

- Global CS = (VFD, PXA) as shared observable knowledge state
- Possible histories / ordering constraints on which CS states can precede others
- *Source: `docs/topics/process_models/cs/transitions.md`; `docs/topics/possible_histories.md`*

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
| `LAPSED` | Timeout (pocket veto) | `DECLINED` |
| `DECLINED` | Case owner re-invites | `INVITED` |
| Any | EM exits (`EXITED`) | `NO_EMBARGO` (RESET) |

- *Source: `notes/participant-embargo-consent.md`; `specs/case-management.yaml` CM-18; ADR-0048*

#### 6.4.3 Semantics of `NO_EMBARGO`

- `NO_EMBARGO` means **absence of an embargo context**, not "not yet consented"
- Direct `ACCEPT` and `DECLINE` from `NO_EMBARGO` are valid (no invitation
  required) to accommodate self-determined embargoes and implicit reporter consent
- The transition `SIGNATORY → INVITED` MUST be rejected (consent cannot be
  retroactively un-given by re-invitation)
- *Source: ADR-0048; `notes/participant-embargo-consent.md`*

#### 6.4.4 Pocket Veto (Timer-Based Transitions)

- `INVITED → DECLINED` and `LAPSED → DECLINED` are timer-based
- Timeout window is a configurable policy option (per-case or global)
- *Source: `notes/participant-embargo-consent.md` §"Pocket Veto"*

#### 6.4.5 Embargo Meta-Protocol Delivery to Non-Signatories

- Embargo meta-protocol messages (`Offer`, `Invite`, `Announce` of
  `EmbargoEvent`) MUST be delivered even to `DECLINED` and `LAPSED` participants
- Only case content (report details, fix status, sensitive notes) is gated on
  `SIGNATORY` status
- *Source: `notes/participant-embargo-consent.md`*

#### 6.4.6 Relationship to `embargo_adherence`

- `embargo_adherence` is a derived property: `True` iff PEC = `SIGNATORY`
- Full case delivery (`Announce(VulnerabilityCase)` with sensitive content)
  requires both `RM = ACCEPTED` and `embargo_adherence = True` (or no active embargo)
- *Source: `specs/case-management.yaml` CM-10, CM-18*

### 6.5 Model Interactions and Cascade Rules

State transitions in one dimension can trigger obligations in others.
Key cascades:

- **RM acceptance → CS broadcast**: when a participant's RM reaches `ACCEPTED`,
  the Case Actor MUST send `Announce(VulnerabilityCase)` with full case content
  (subject to embargo adherence check — §6.4.6)
- **EM enters REVISE → bulk PEC lapse**: all participants currently at PEC
  `SIGNATORY` MUST be transitioned to `LAPSED`
- **EM exits → PEC reset**: all participants' PEC machines MUST be reset to
  `NO_EMBARGO`
- **PXA observation adopted → embargo teardown**: canonical adoption of any
  status carrying CS.P, CS.X, or CS.A MUST trigger embargo teardown evaluation
  (see §7.4.2 Seam 2)
- **Embargo teardown → CS broadcast**: termination of an active embargo
  SHOULD trigger a fresh `Announce(CaseStatus)` to all participants

Cascades are event-driven: a state change produces a domain event that the
Case Actor's behavior tree handles. The BT structure ensures cascades fire
in the correct order and that each step is independently authorizable.

- *Source: `notes/protocol-event-cascades.md`; `specs/event-driven-control-flow.yaml`;
  `notes/received-status-authorization.md`*

### 6.6 Participant Lifecycle Within a Case

- Invitation, acceptance, role assignment, removal
- Case ownership and transfer
- *Source: `specs/case-management.yaml`; `notes/ownership-transfer.md`*

---

## 7. Conformance [N]

### 7.1 Conformance Model Overview

Conformance is two-dimensional: a **capability level** (which state machines
an implementation supports) and a **role profile** (which process and
coordination roles it claims). A conformance claim takes the form:

> `L{n} / Role [+ Role ...]`

Examples: `L1 / Reporter`, `L2 / Vendor`, `L2 / Vendor + Deployer`,
`L3 / Coordinator + CNA`, `L3 / Coordinator + Case Owner`.

Capability levels are cumulative: L2 implies L1; L3 implies L2 and L1.
Role obligations are additive and orthogonal: no role subsumes another.

### 7.2 Capability Levels

#### L0 — Observer

- MUST be able to receive and parse all Vultron message types
- No state machine implementation required
- No send obligations
- The minimum to be "in" a case without acting on it
- Holds the Observer process role

#### L1 — Report Participant

- MUST implement the RM state machine
- MUST send the messages appropriate to claimed process roles when the
  corresponding RM transitions occur
- MUST receive and track RM state changes notified by other participants
- *Source: `specs/vultron-protocol-spec.yaml`; `specs/state-machine.yaml`*

#### L2 — Embargo Participant

- All L1 requirements, plus:
- MUST implement the EM state machine (case-level collective embargo state)
- MUST implement the PEC state machine (per-participant consent tracking)
- MUST participate in embargo negotiation: sending and responding to
  `Offer(EmbargoEvent)`, `Accept`, `Reject` as appropriate to role
- MUST deliver embargo meta-protocol messages to all participants regardless
  of their PEC state (see §6.4.5)
- *Source: `specs/embargo-policy.yaml`; `specs/case-management.yaml` CM-18*

#### L3 — Coordinator

- All L2 requirements, plus:
- MUST implement the CS state machine (VFD + PXA dimensions)
- MUST broadcast CS state changes to case participants via `Announce(CaseStatus)`
- MUST implement multi-party case management: participant invitation,
  acceptance, role assignment, case ownership
- MUST implement case ledger replication
- *Source: `specs/sync-ledger-replication.yaml`; `specs/case-management.yaml`*

### 7.3 Role Taxonomy

#### 7.3.1 Process Roles (capability set labels)

Process roles define what an actor *does* and which protocol transitions it
is authorized to drive. An actor may hold multiple process roles.

| Role | Protocol capability |
|---|---|
| Observer | Receive and parse; no send obligations; may emit participant-agnostic CS observations (see §7.4.2) |
| Reporter | Initiates cases; drives `RS`; authoritative source of the original report |
| Vendor | Drives participant-specific VFD transition `f→F` (fix ready, `CF`) |
| Deployer | Drives participant-specific VFD transition `d→D` (fix deployed, `CD`) |
| Coordinator | Drives case participant management; coordinates multi-party disclosure |
| CNA | May directly assign CVE IDs; non-CNA delegates to an external CNA service. Orthogonal to other roles — typically co-held with Coordinator or Vendor |

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

### 7.4 Role-Specific Normative Requirements

#### 7.4.1 Participant-Specific CS Transitions (VFD)

VFD tracks what a specific participant has *done*. Transitions are gated by
role and MUST NOT be driven by actors lacking the required role:

- `f→F` (VFd, fix ready): MUST only be driven by an actor holding Vendor
- `d→D` (VFD, fix deployed): MUST only be driven by an actor holding Deployer
- A Vendor-only actor MUST NOT advance past VFd without also holding Deployer
- *Source: `specs/cs-behavior.yaml` CSB-15-001, CSB-15-002*

#### 7.4.2 Participant-Agnostic CS Transitions (PXA)

PXA tracks the state of the world. Any participant — including an Observer —
MAY emit observations of PXA state changes. These transitions are ungated
because information about the vulnerability may become public, exploits may
appear, or attacks may be observed independently of any participant's actions
and independently of whether any case participant caused them:

- `p→P` (publicly aware): any participant may report
- `x→X` (exploit public): any participant may report
- `a→A` (attacks observed): any participant may report

A participant that monitors external sources (threat feeds, public disclosures,
vulnerability databases) and reports observations to a case is called a
**sentinel**. The sentinel pattern is the intended production mechanism for
PXA observations that originate outside the case.

PXA observation adoption is governed by a two-seam authorization model:

**Seam 1 — Adoption** (`StatusUpdateGuard`):

A participant reports a PXA observation via `Add(ParticipantStatus)`. The
receiving Case Actor evaluates whether to treat the reported state as canonical:

- A Case Owner's observation MUST be adopted without requiring approval
- All other senders are subject to a configurable approval gate; the default
  policy is to auto-adopt
- If adopted, the Case Actor emits `Add(CaseStatus)` to itself as Case
  Manager to canonicalize the state

**Seam 2 — Side-effects** (`SideEffectsGuard` + `ThreatTerminationBranchNode`):

After canonical adoption, the Case Actor evaluates whether to execute
side-effects:

- MUST check whether the canonical status carries CS.P, CS.X, or CS.A
- If any of these are present, MUST initiate embargo teardown
- This check MUST run after the canonical write, not before
- A second configurable gate MAY require additional approval before executing
  teardown; the default is to proceed automatically

The two seams are independent: the adoption decision does not know about
teardown, and the side-effects decision does not know whether the canonical
write came from an external message or an internal self-emit.

- *Source: `notes/received-status-authorization.md`; ADR-0046;
  `specs/received-status-handling.yaml` RSH-01–RSH-03*

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
- *Source: `notes/behavioral-conformance-specs.md`*

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

- *Source: `docs/reference/fv-demo-protocol.md`*

### Annex C — Notation Reference [I]

- *Source: `docs/reference/notation.md`*

### Annex D — Possible Case Histories [I]

- Ordering constraints on CS state transitions
- *Source: `docs/topics/process_models/cs/` possible_histories material*

### Annex E — Relationship to ActivityPub [I]

- Where Vultron follows ActivityPub and where it diverges
- *Source: `notes/activitystreams-semantics.md`*

### Annex F — Behavior Tree Reference Implementation [I]

- BTs as one valid implementation pattern, not normative
- *Source: `docs/topics/behavior_logic/`*

---

## Open Questions (to resolve before circulating)

1. **Namespace URI** — Is there a stable `vultron:` or `https://vultron.example/`
   namespace ready to cite?
2. **Sync/replication** — Is the ledger replication protocol in scope for this
   RFC, or a separate companion spec? (Currently placed at L3 but could be split
   out.)
3. ~~**ActivityPub vs. bare AS2**~~ — Resolved for this version. §4.1 states the
   current normative floor as AS2 vocabulary only, with an informative note that
   a future version is expected to require full ActivityPub conformance at L1+.
   Tracked in issue #2068.
4. **Background material depth** — How much CVD domain background belongs here
   vs. a companion "CVD Concepts" document?
5. **Finder removal ADR** — Decision to drop the Finder role needs an ADR before
   the spec circulates. Rationale: Reporter is the protocol-salient role; Finder
   identity may be recorded in the report or case Notes but has no protocol effect.
6. **Observer rename ADR** — Decision to rename Other → Observer similarly needs
   an ADR, and the enum change needs an issue.
7. ~~**PXA adoption policy**~~ — Resolved. Two-seam model specified in §7.4.2:
   Seam 1 (adoption via `StatusUpdateGuard`) and Seam 2 (side-effects via
   `ThreatTerminationBranchNode`). Source: `notes/received-status-authorization.md`,
   ADR-0046.
8. **L0 Observer in case** — How does an Observer get *into* a case? Presumably
   by invitation from a Case Owner or Case Manager. The invitation flow for a
   role-less participant needs to be specified.
9. **CNA eligibility criteria** — The CVE ID assignment tree encodes CNA
   Operational Rules v4.1.0 criteria inline. Should the RFC cite these as
   normative external requirements, or treat the eligibility checks as
   implementation-defined?
