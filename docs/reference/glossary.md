# Ubiquitous Language — Vultron

Domain terminology for Vultron's Coordinated Vulnerability Disclosure (CVD)
protocol and hexagonal architecture. Extracted from codebase models, state
machines, and design notes.

---

## Core CVD Concepts

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Vulnerability** | A weakness in an information system that could be exploited to cause harm | Bug, issue, flaw |
| **Coordinated Vulnerability Disclosure (CVD)** | A collaborative process where affected parties work together to manage vulnerability remediation and public disclosure | Responsible disclosure, coordinated release |
| **Multi-Party CVD (MPCVD)** | CVD process involving three or more independent organizations with different interests and roles | Multiparty coordination |
| **Report** | A formal notification of a discovered vulnerability, including technical details and potential impact | Submission, notice |
| **Case** | A federated container tracking all parties, state, communications, and embargo agreements related to a specific vulnerability across multiple organizations | Issue, coordination event |

---

## CVD Roles and Participants

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Finder** | The person or organization that discovers a vulnerability | Researcher, discoverer |
| **Reporter** | The person or organization that submits a vulnerability report to affected parties (often the same as Finder) | Submitter, notifier |
| **Vendor** | The organization that maintains or supplies the affected product or service | Developer, supplier, maintainer |
| **Deployer** | An organization that deploys the Vendor's product and is responsible for applying patches in their own environment (distinct from Vendor) | Operator, customer |
| **Coordinator** | A neutral third party (often a national CERT) that facilitates communication and negotiates embargo terms between other parties | Mediator, facilitator |
| **Participant** | Any Actor engaged in a Case, holding one or more CVD Roles | Stakeholder, party |
| **Actor** | Any URI-identified federated peer (person or organization) in the protocol | Agent, endpoint |
| **Case Owner** | The Actor who creates and administers a Case (typically the party seeking vulnerability coordination) | Case creator |
| **Case Actor** | An auto-generated federated peer (ActivityStreams Service actor) created during case initialization; operates as the single-writer authority for the canonical case log and coordinates state across participants | Case service actor, case coordinator |
| **Case Manager** | A **CVDRoles** role flag (part of **CVDRoles** bitmask) that designates a **Participant** authorized to delegate case management responsibilities and co-manage embargo negotiations; often assigned via **Offer** → **Accept** handoff during case creation | Admin role, management role |

---

## Case State Model (Six Dimensions)

The **Case State (CS)** tracks awareness and readiness across six binary dimensions:

| Abbreviation | Uppercase | Lowercase | Meaning |
|---|---|---|---|
| **V/v** | **V** | **v** | Vendor is aware / unaware |
| **F/f** | **F** | **f** | Fix is ready / not ready |
| **D/d** | **D** | **d** | Fix is deployed / not deployed |
| **P/p** | **P** | **p** | Public is aware / unaware |
| **X/x** | **X** | **x** | Exploit code is public / not public |
| **A/a** | **A** | **a** | Active attacks have been observed / not observed |

Each transition from lowercase to uppercase represents an event; once uppercase,
it cannot revert. This forms a 64-state lattice (2^6 combinations).

---

## State Machines and Status

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Report Management (RM)** | Per-participant state machine tracking a Report's lifecycle: Start → Received → {Invalid \| Valid} → {Accepted \| Deferred} → Closed; independent for each participant | Report workflow, report state |
| **Embargo Management (EM)** | Global (per-case) state machine tracking embargo coordination: None → Proposed ↔ Active ↔ Revise → eXited; exactly one active embargo per case | Embargo workflow, embargo state |
| **Case State (CS)** | Hybrid state model tracking both participant-specific vendor fix path (vfd→Vfd→VFd→VFD) and participant-agnostic public state (pxa combinations); 40 total states | Vulnerability state, case lattice |
| **Case Status** | A snapshot of RM, EM, and CS state at a specific moment, with a timestamp and attribution | State record |
| **Participant Status** | A snapshot of a Participant's RM state and embargo consent, recording their role and commitment at a specific moment | Status record |
| **State Transition** | A move from one valid state to another in the RM, EM, or CS machine; always forward (events cannot be undone) | State change, event |
| **Communicating Hierarchical State Machine** | The formal protocol architecture: N independent processes (Participants) coordinating state transitions through message passing | Protocol model, message-driven coordination |
| **Composite State** | A Participant's complete state, represented as a 3-tuple: (q^cs, q^rm, q^em) | Participant state, actor state |

---

## Embargo and Timing

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Embargo** | A time-bounded agreement that participating parties will not publicly disclose a vulnerability until a specific date or condition is met | NDA, disclosure delay, embargo period |
| **Embargo Event** | A point-in-time record of an embargo's end date, context, and who initiated it; used to track embargo history | Embargo record |
| **Embargo Consent** | A **Participant**'s individual agreement to or rejection of a proposed **Embargo** (a personal commitment, distinct from the **Embargo** itself); tracked as a per-participant 5-state machine: NO_EMBARGO → INVITED ↔ SIGNATORY ↔ LAPSED → DECLINED | Embargo acceptance, embargo stance |
| **Active Embargo** | The currently in-force **Embargo** for a **Case**; there is at most one | Current embargo, ongoing embargo |
| **Proposed Embargo** | An **Embargo** that has been offered but not yet accepted by all parties | Embargo offer, pending embargo |
| **Pocket Veto** | A timer-based transition in the **Embargo Consent** state machine where a **Participant** in INVITED or LAPSED state automatically transitions to DECLINED if they do not respond within a configurable timeout window (inaction = rejection) | Embargo invitation timeout, implicit rejection |

---

## Messaging and Protocol

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Semantic Type** (or **MessageSemantics**) | The classification of an Activity's meaning (e.g., `CreateReport`, `AcceptEmbargoOnCase`, `ProposeEmbargo`); determines how it is processed | Activity type, message type |
| **Message Type** | One of 29 formal protocol message categories: RM messages (RS, RI, RV, RD, RA, RC, RK, RE), EM messages (EP, ER, EA, EV, EJ, EC, ET, EK, EE), CS messages (CV, CF, CD, CP, CX, CA, CK, CE), or General (GI, GK, GE) | Protocol message category |
| **State-Change Notification** | The core protocol principle: every participant state transition SHOULD generate a message to inform other participants; implements "Avoid Surprise" | Status announcement, state broadcast |
| **Inbox** | The protocol endpoint where an Actor receives incoming Activities from other parties | Receiver, endpoint |
| **Outbox** | The protocol channel through which an Actor broadcasts Activities to other known parties | Sender, distribution |
| **Precondition** | The required state(s) that must be true before a message can be sent or a state transition is valid (e.g., Participant must be in RM Accepted to send RS) | State requirement, prerequisite |

---

## Data and Relationships

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Case Activity Log** | A list of Activity IDs associated with a Case, recording the protocol history without storing full Activity payloads | Activity history, message log |
| **Case Event** | A trusted-timestamp record of a protocol-relevant state change (V, F, D, P, X, A event), recorded when a handler processes an incoming Activity | Event, state change record |
| **Note** | Unstructured text attached to a Case by a Participant; used for comments, observations, and negotiation | Comment, annotation, memo |
| **Parent/Child/Sibling Cases** | Hierarchical relationships between Cases: a Case can split (children) or merge (parent); siblings share a common parent | Case relationships, case graph |

---

## Hexagonal Architecture & Abstraction

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Port** | An interface contract that abstracts a capability; core modules depend on ports, not concrete implementations | Interface, contract, API |
| **Adapter** | A concrete implementation of a port; lives in the adapter layer and translates between external systems and the core domain | Implementation, provider |
| **Narrow Port** | A port with a small, typed, domain-specific interface (e.g., `CasePersistence`, `CaseOutboxPersistence`, `ActivityTranslator`) designed for a single responsibility; replaces broad generic ports for improved type safety and testability | Constrained port, domain port, semantic port |
| **Broad Port** | A port with a large, generic, untyped interface (e.g., legacy `DataLayer` with `get(table, id)`, `by_type(type)`) that couples core to lower-level storage details; marked for replacement by **Narrow Ports** | Generic port, legacy port |
| **Driven Port** | A port that exposes an outbound dependency; core calls it to reach adapters (e.g., `DataLayer`, `ActivityTranslator`) | Dependency port, outbound port |
| **Driving Port** | A port that exposes an inbound boundary; adapters call it to reach core (e.g., use cases, handlers) | Inbound port, entry point |
| **Hexagonal Architecture** | Layered design where core business logic has no imports from wire format, adapter, or external framework layers | Ports and adapters, onion architecture |

## Sync, Authority & Replication

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Log-Centric Architecture** | A system design where the **CaseActor** is the authoritative single writer of an append-only, hash-chained **canonical recorded log**, and all externally visible replicated state is a deterministic projection of that log | Log-based architecture, event sourcing |
| **Single-Writer Regime** | The design principle that the **CaseActor** (acting as de facto replication leader) is the only node that appends to the authoritative **canonical recorded log**; simplifies consistency guarantees and avoids concurrent-write conflicts | Single leader, master authority |
| **Canonical Recorded Log** | The authoritative append-only history maintained by the **CaseActor**; hash-chained for verification; replicated to **Participants** via `Announce(CaseLogEntry)` messages | Authoritative log, master log |
| **Case Log Entry** | A single item in the **canonical recorded log**; includes a trusted timestamp generated by the **CaseActor** (never copied from inbound **Activities**), hash of its content, and hash of its predecessor (forming a Merkle chain) | Log item, journal entry |
| **Eventual Consistency** | The replication guarantee that **Participant** replicas converge to the **CaseActor**'s state as **Case Log Entries** are delivered and processed | Convergence property |
| **Participant Case Replica** | A local copy of **VulnerabilityCase** state maintained by a **Participant** node; must satisfy PCR safety rules (proper seeding, no out-of-order mutations) and convergence to the **CaseActor**'s authoritative state | Case replica, local case copy |
| **Trust Bootstrap** | The first-time establishment of trust between the **CaseActor** and a new **Participant** via an **Accept** activity in response to an **Offer**; includes sending a `Create(VulnerabilityCase)` activity to seed the **Participant Case Replica** | Trust handoff, initial trust |
| **Case Replica Seeding** | The process of initializing a **Participant Case Replica** by receiving an `Announce(VulnerabilityCase)` or `Create(VulnerabilityCase)` activity from the **CaseActor**; must occur before case-context activities can be processed | Replica initialization, case sync |

## Activity & Wire Format

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Activity** | A Vultron protocol message in ActivityStreams 2.0 JSON format; represents a state change notification (Create, Accept, Reject, etc.) | Message, notification, AS2 object |
| **Inbound Activity** | An **Activity** received at the inbox from a remote actor; must be parsed, pattern-matched, and semantically extracted | Received message |
| **Outbound Activity** | An **Activity** constructed by a use case and queued in an outbox for delivery to remote actors; MUST include full inline objects and a non-empty `to:` field per **Actor Knowledge Model** | Sent message, outgoing activity |
| **ActivityPattern** | A template for matching an inbound **Activity** structure; used to extract semantic intent (e.g., a `CreateReport` vs an `AcceptInvite`) | Matcher, pattern, discriminator |
| **Semantic Extraction** | The process of mapping an inbound **Activity** structure to a domain-level **MessageSemantics** enum value | Pattern matching, dispatch, intent detection |
| **MessageSemantics** | A domain-level enum of message intents (e.g., `CREATE_REPORT`, `ACCEPT_INVITE_TO_EMBARGO_ON_CASE`) | Message type, semantic type, intent |
| **Factory Function** | A public, type-safe constructor function that builds outbound **Activities**; ensures validation and returns plain AS2 types; located in `vultron/wire/as2/factories/` | Activity constructor, builder |
| **from_core()** | A wire-layer method that constructs wire objects from domain objects; should only be called from adapters, not core use cases (architecture violation: ARCH-03-001) | Wire constructor |
| **Stub Object** | A lightweight object representation in ActivityStreams 2.0 containing only `id`, `type`, and optionally `summary` fields; used for selective disclosure (e.g., restricting vulnerability details pending embargo acceptance) | Lazy-loaded object, header-only object, object reference |
| **Activity Translator** (port) | A narrow driven port that core use cases call to construct outbound **Activities** from domain objects; implemented by adapters with wire imports, preserving core layer isolation (inverse of `from_core()` anti-pattern) | Wire adapter port, activity constructor port |

## Persistence & Data Access

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **DataLayer** | A broad, generic persistence port that core modules use to store and retrieve case data; provides raw `dict` access | Persistence, storage, database |
| **CasePersistence** | A narrow, typed persistence port for case-specific queries; replaces broad `get()`/`by_type()` with domain-specific methods like `read_by_id()` and `list_by_status()` | Case DAO, case repository |
| **CaseOutboxPersistence** | A narrow, typed persistence port for outbox (outbound activity queue) queries; separate from case data | Outbox DAO, outbox repository |
| **Auto-Rehydration** | The design contract that `dl.read()` and `dl.list_objects()` MUST return fully typed, rehydrated domain objects (never raw storage records or dehydrated string references), eliminating the need for `model_validate()` coercion in use cases | Automatic deserialization, typed retrieval |
| **Rehydration** | The process of deserializing raw persisted records (dicts) into typed domain objects (Pydantic models) | Deserialization, model coercion, casting |
| **Compatibility Method** | A deprecated method (`get()`, `by_type()`) still present for backward compatibility but marked for removal | Escape hatch, legacy method |
| **Actor Knowledge Model** | The architectural invariant that an **Actor**'s knowledge of the world is bounded only by what it has **received** via AS2 **Activities**; recipients cannot access senders' DataLayers; therefore, all outbound **Activities** MUST include full inline objects, never bare URIs | Knowledge boundary, isolation invariant |
| **Bare Object URI** | An anti-pattern in outbound **Activities** where an object is referenced as a bare string URI (e.g., `object_="urn:uuid:abc123"`) instead of a full inline object; causes recipient pattern-matching failure because the recipient's DataLayer has no record of the referenced object | String reference, bare ID |

## Behavior Trees

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **BT** | A Behavior Tree; a state machine implementation using py_trees that orchestrates domain logic and protocol events | State machine, tree, orchestrator |
| **Node** | A component in a **BT** that extends `Behavior` and implements a single domain action (e.g., create a participant, attach a note) | Action, task |
| **Blackboard** | Global shared state storage for **BT** nodes to read/write data during execution; keys use `{noun}_{id_segment}` format to avoid py_trees path parsing issues | Shared memory, context |
| **BTTestScenario** | A deep-module test harness that eliminates boilerplate setup; allows BT node tests to be written without repeating blackboard initialization | Test fixture, test helper |
| **Trunk-Removed Branches Model** | The prototype BT architecture that mirrors the canonical simulation BT structure by exposing individual subtrees as event-driven use cases triggered by incoming **Activities**, rather than a continuous-tick monolithic root tree | Branched event model, handler-first BTs |
| **Protocol-Significant Behavior** | Any action that affects protocol-observable state (emitting an **Activity**, transitioning RM/EM/CS, cascading consequences); MUST be implemented as BT nodes/subtrees, never as procedural code outside the tree | Domain logic, tree-resident behavior |
| **Cascading Consequences** | Automated downstream behaviors triggered by primary protocol events via BT subtrees; examples include submit-report → case creation → participant setup → embargo initialization → notifications (anti-pattern: post-BT procedural calls) | Event cascade, automation chain |

## Domain Model — CVD Coordination

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **CVDRole** | A StrEnum representing individual, atomic CVD roles (FINDER, REPORTER, VENDOR, DEPLOYER, COORDINATOR, OTHER, CASE_OWNER, CASE_MANAGER); participants hold zero or more roles represented as `list[CVDRole]`; preferred representation for new code (replaces legacy bitmask) | Role value, role enum |
| **CVDRolesFlag** | Legacy bitmask-based Flag enum using bitwise arithmetic to represent combined roles; retained for backward compatibility with the `vultron.bt` simulator layer only; **do not use in new code** — use `list[CVDRole]` instead | Bitmask roles, legacy roles |
| **CASE_OWNER** | A **CVDRole** value marking a participant as the human decision-maker who owns and administers the VulnerabilityCase (BTND-05-001); distinct from CASE_MANAGER which is the service actor | Owner role |
| **CASE_MANAGER** | A **CVDRole** value representing the ActivityStreams Actor (often a Service type) that performs ongoing case replica synchronization and manages the case on behalf of the **Case Owner**; always held alongside the COORDINATOR role (CBT-01-003); may be any Actor type though demo uses Service | Case synchronizer, case service actor |
| **Participant** | A CVD actor in a case; has one or more **CVDRole** values, contact info, and status in the case state machine | Actor, stakeholder |
| **Embargo Initialization** | The automatic creation of a default **Embargo** with standard terms when a **Case** is first created; includes seeding the **Case Owner** as **Participant** with SIGNATORY **Embargo Consent** status | Default embargo creation, embargo bootstrap |
| **Role Delegation** | The protocol sequence where a **Case Owner** can offer the **CASE_MANAGER** role to another **Participant** (via **Offer** activity) and receive acceptance (via **Accept** activity); enables distributed case administration | Role handoff, role transfer |

## Architecture Compliance & Violations

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **ARCH-03-001** | Architectural rule: core modules MUST NOT import from the wire layer (AS2, activity constructors, wire vocab) | Architecture constraint, import rule |
| **Hexagonal Violation** | A break of the hexagonal architecture rule where core calls wire-layer constructors (e.g., `from_core()` called from use cases); must be fixed | Layer boundary break, import violation |

---

## CVD Domain Ambiguities (Flagged)

1. **"State" (multiple meanings)**:
   - The **Case State (CS)** — the six-dimensional VfDpxa lattice model
   - A **Case Status** — a snapshot of CS, RM, and EM at one moment
   - An RM or EM state — a specific state machine location
   - **Recommendation**: Prefer precise terms. Use "Case State" for the 64-node lattice; "Case Status" for a snapshot; "RM state" or "EM state" for a specific state machine location.

2. **"Participant" vs. "Actor"**:
   - An **Actor** is any URI-identified federated peer (a role in the protocol).
   - A **Participant** is an Actor actively engaged in a specific **Case**.
   - A **Reporter** is both an **Actor** (in general) and might be a **Participant** (in a specific Case).
   - **Recommendation**: Use "Actor" when discussing federation; use "Participant" when discussing a specific Case.

3. **"Report" vs. "Case"**:
   - A **Report** is a one-time vulnerability notification from a **Reporter**.
   - A **Case** is the ongoing coordination container that may span multiple **Reports** (if consolidated) or multiple **Cases** (if split).
   - **Recommendation**: "Report" = inbound vulnerability notification; "Case" = coordination event with state machines and participants.

4. **"Embargo" vs. "Embargo Consent"**:
   - An **Embargo** is a shared agreement (one per **Case**) that all parties will not disclose until a certain date.
   - **Embargo Consent** is each **Participant**'s individual acceptance or rejection of that embargo.
   - **Recommendation**: If discussing terms, say "Embargo"; if discussing one party's stance, say "Embargo Consent".

5. **"Activity" direction** — The term **Activity** is used for both **Inbound** and **Outbound**. Both
   follow ActivityStreams 2.0 format, but context determines meaning.
   - **Recommendation**: Always qualify as "inbound **Activity**" or "outbound **Activity**" when direction matters.

6. **"Factory" scope** — The term **Factory** can mean:
   - The set of **Factory Functions** in the `vultron/wire/as2/factories/` package (public API)
   - A single **Factory Function** (e.g., `create_report()`)
   - **Recommendation**: Say **Factory Function** or **factories package**, never generic "factory".

---

## Work Tracking & Tasks

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **RFC** | Request for Comments; an architecture improvement proposal tracked as a GitHub Issue (e.g., RFC-400, RFC-403) | Architecture proposal, enhancement |
| **TASK** | An implementation task tracked in `plan/IMPLEMENTATION_PLAN.md` (e.g., `TASK-AF`, `TASK-CP-CLEANUP`) | Implementation work, story |
| **Subtask** | A smaller decomposed unit of work within a **TASK** (e.g., AF.1, AF.2, CP-CLEANUP.1) | Sub-work, phase, step |
| **Blocker** | A dependency or prerequisite that prevents a **TASK** from starting (e.g., TASK-AF blocks TASK-ARCHVIO) | Dependency, prerequisite |
| **Acceptance Criteria** | The must-satisfy conditions for a **TASK** or **Subtask** to be considered complete | Definition of done, requirements |
| **Priority 473** | Architecture Hardening: an initiative to deepen module design, reduce coupling, and improve testability via RFCs and narrowing ports | Sprint, milestone, epic |

---

---

---

## Formal Protocol Concepts

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Deterministic Finite Automaton (DFA)** | A mathematical model representing a state machine with finite states, an initial state, final states, input symbols (transitions), and transition functions; the formal foundation for RM, EM, and CS models | State machine, FSM |
| **Process** | In protocol formalism, an independent entity (Participant) maintaining its own state and communicating with other processes via messages | Actor, participant |
| **Global State** | The complete system state comprising all N participants' composite states plus all messages in flight between them | System state, protocol state |
| **Message Queue** (or **Channel**) | A FIFO buffer from Participant i to Participant j containing ordered messages; denoted C_ij in formal notation | Message buffer, transport channel |
| **Reachable State** | A state logically possible for a Participant given protocol constraints (not all 1,400 theoretical states are reachable) | Valid state, achievable state |
| **Unreachable State** | A state impossible due to protocol constraints (e.g., RM Start/Closed states make EM and CS irrelevant) | Invalid state, forbidden state |
| **Ordering Preference** | One of 12 formally-defined preferences for CVD outcomes (e.g., D ≺ P: Fix Deployed Before Public Awareness); guides protocol design | Success metric, outcome goal |
| **Avoid Surprise** | Core CVD principle embedded in protocol: participants whose state changes SHOULD send messages to other participants to minimize surprise | Transparency principle, communication imperative |

---

## RM Model Details

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Report Submission (RS)** | The only RM message that directly triggers a state change in receiver (from S → R); all other RM messages announce sender's state | Initial RM message |
| **Report Received (R)** | Initial RM state when a Report arrives; recipient must validate before transitioning to Invalid or Valid | Received state, intake state |
| **Report Valid (V)** | RM state indicating validation passed; next decision is whether to Accept or Defer | Validated state, prioritization state |
| **Report Accepted (A)** | RM state indicating work accepted; prerequisite for sending RS to other parties | In-progress state, active state |
| **Report Deferred (D)** | RM state indicating work deferred (parking lot); can transition back to Accepted if priorities change | Parked state, backlog state |
| **Report Closed (C)** | Final RM state; recipient may ignore all messages on closed reports (no further coordination) | Terminal state, archive state |

---

## EM Model Details

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Embargo None (N)** | EM initial state; no embargo currently in effect or agreed to | Initial state, no-embargo state |
| **Embargo Proposed (P)** | EM state indicating one or more embargo proposals under negotiation | Pending state, negotiation state |
| **Embargo Active (A)** | EM state indicating embargo is in effect across all participants; only one per case | Effective state, in-force state |
| **Embargo Revise (R)** | EM state indicating active embargo with revision proposal pending; active embargo remains in force until revision accepted | Renegotiation state, revision-pending state |
| **Embargo eXited (X)** | EM terminal state after embargo terminates (by expiration, early termination, or public disclosure) | Expired state, terminated state |
| **Embargo Proposal (EP)** | EM message type proposing embargo terms (e.g., expiration date) | Embargo offer |
| **Embargo Termination (ET)** | EM message type terminating embargo immediately; has immediate effect regardless of other pending messages | Embargo end, embargo expiration |
| **Embargo Grammar** | Regular expression `(p*r)*(pa(p*r)*(pa)?t)?` describing all valid EM state transition sequences | DFA language, EM language |

---

## CS Model Details

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Vendor Fix Path** | Participant-specific CS submodel tracking vendor awareness (v/V), fix readiness (f/F), fix deployment (d/D); one path per Vendor | Vendor progression, fix progression |
| **Public State** | Participant-agnostic CS submodel tracking public awareness (p/P), exploit public (x/X), attacks observed (a/A); shared across all participants | Global state, pxa state |
| **Vendor Awareness (V)** | CS event: transition from vendor unaware (v) to vendor aware (V); typically triggered by Report Submission | V event, vendor notification |
| **Fix Readiness (F)** | CS event: transition from fix not ready (f) to fix ready (F); indicates vendor has completed fix development | F event, fix development complete |
| **Fix Deployed (D)** | CS event: transition from fix not deployed (d) to fix deployed (D); indicates vendor/deployer has applied fix | D event, fix application |
| **Public Awareness (P)** | CS event: transition from public unaware (p) to public aware (P); indicates vulnerability known outside immediate parties | P event, disclosure |
| **Exploit Public (X)** | CS event: transition from exploit not public (x) to exploit public (X); indicates exploit code publicly available | X event, exploit disclosure |
| **Attacks Observed (A)** | CS event: transition from attacks not observed (a) to attacks observed (A); indicates active exploitation in the wild | A event, active attack |
| **vfd·· notation** | Compact notation for CS states where lowercase/uppercase in each position represents specific substate (v=vendor unaware, V=aware, f=fix not ready, F=ready, etc.) | State shorthand, state code |
| **pxa notation** | Public state substates abbreviated as p/P (public aware), x/X (exploit public), a/A (attacks observed) | Public substate |
| **Ephemeral State** | CS constraint: exploit public without vulnerability public (···pX·) cannot exist; immediately resolves to ···PX· | Transient state, immediate transition |

---

## Relationships

**Protocol Structure:**

- A **Communicating Hierarchical State Machine** consists of N independent **Processes** (Participants) coordinating via message passing.
- Each **Process** maintains a **Composite State** = (**Case State** + **RM State** + **EM State**).
- The **Global State** includes all **Composite States** plus message queues (**Channels**) between processes.

**State Transitions:**

- RM transitions are mostly independent; only **Report Submission (RS)** directly changes receiver RM state.
- EM transitions are global; exactly one **EM State** per case affects all participants.
- CS transitions are hybrid: **Vendor Fix Path** is per-Vendor; **Public State** is global.

**Message Protocol:**

- **State-Change Notification**: each state transition SHOULD emit a **Message Type** to other participants.
- RM messages: RS is unique (triggers receiver state); others announce sender status (RI, RV, RD, RA, RC).
- EM messages: all trigger global EM state updates (EP, EA, ER, EV, EC, EJ, ET).
- CS messages: announce **CS Events** (CV, CF, CD, CP, CX, CA).
- All valid messages receive acknowledgments (RK, EK, CK, GK); errors generate (RE, EE, CE, GE).

**Constraints:**

- **Precondition**: Participant must be in RM Accepted (A) to send RS.
- **Single Embargo**: exactly one **Embargo Active (A)** per case.
- **Public Embargo Boundary**: no EM negotiation when **Public Awareness (P)** or **Exploit Public (X)** or **Attacks Observed (A)** occur.
- **Reachable States**: many of 1,400 theoretical **Composite States** are **Unreachable** due to constraints.

**Success Metrics:**

- 12 **Ordering Preferences** define CVD success; **Embargo Active** is primary mechanism for achieving top preferences (D ≺ P, F ≺ P).

**Architecture Integration:**

- A **Port** is implemented by one or more **Adapters**.
- **Inbound Activities** are matched by **ActivityPatterns** to extract **MessageSemantics** (formal protocol **Message Type**).
- **Outbound Activities** are constructed by **Factory Functions** (not by core calling `from_core()`).
- A **TASK** may be blocked by another **TASK** via a **Blocker**.
- A **TASK** contains one or more **Subtasks** with **Acceptance Criteria**.
- **CasePersistence** and **CaseOutboxPersistence** replace the broad **DataLayer** interface for core use cases.
- **Rehydration** converts raw persisted dicts (from **DataLayer**) into typed domain objects.
- A **Participant** has zero or more **CVDRoles** (represented as **CVDRoles** bitmask; will become `list[CVDRoles]` after TASK-BTND5.4).
- A **BT Node** reads from and writes to the **Blackboard** and may emit **Outbound Activities**.

---

## Flagged Ambiguities

1. **"State" (multiple meanings)**:
   - The **Case State (CS)** — the 40-state lattice combining **Vendor Fix Path** (vfd, Vfd, VFd, VFD, ∅) and **Public State** (pxa combinations).
   - An **EM State** — a single Embargo Management state (None, Proposed, Active, Revise, eXited).
   - An **RM State** — a single Report Management state (Start, Received, Invalid, Valid, Accepted, Deferred, Closed).
   - A **Composite State** — a participant's complete state tuple (q^cs, q^rm, q^em).
   - A **Case Status** — a snapshot of all three machine states at one moment.
   - **Recommendation**: Always qualify: "Case State lattice," "EM State," "RM State," "Composite State," or "Case Status."

2. **"Message" vs. "Activity" vs. "Message Type"**:
   - A **Message Type** is a formal protocol category (e.g., RS, EP, CV) from the 29-message set.
   - An **Activity** is the ActivityStreams 2.0 JSON wire format carrying a **Message Type**.
   - A **State-Change Notification** is the abstract principle that every transition should generate a message.
   - **Recommendation**: Use "Message Type" for protocol formalism; "Activity" for wire transport; "Semantic Type" for the extracted intent.

3. **"Participant" vs. "Actor" vs. "Process"**:
   - An **Actor** is any URI-identified federated peer (federation concept).
   - A **Participant** is an **Actor** actively engaged in a specific **Case**.
   - A **Process** is a formal state machine in the mathematical protocol specification.
   - **Recommendation**: Use "Actor" for federation; "Participant" for case-specific engagement; "Process" for formal protocol math.

4. **"Reachable" vs. "Valid"**:
   - **Reachable** = logically possible given protocol constraints (state might not occur in practice but conforms to rules).
   - **Valid** = permissible per protocol rules (state satisfies all constraints).
   - **Unreachable** = impossible due to hard constraints (violates protocol rules).
   - **Recommendation**: Use "Reachable State" for logical possibility; "Valid Transition" for rule compliance.

5. **"CS Event" vs. "Message Type"**:
   - A **CS Event** (V, F, D, P, X, A) is a formal state transition in the **Case State** lattice.
   - A **Message Type** (CV, CF, CD, CP, CX, CA) is the protocol message announcing that event.
   - Not all **CS Events** are announced (e.g., a Vendor may internally transition Vfd→VFd without sending CF).
   - **Recommendation**: Use "CS Event" for state transitions; "Message Type" for protocol announcements.

6. **"Activity" direction** — The term **Activity** is used for both **Inbound** and **Outbound**. Both follow the same ActivityStreams 2.0 format, but the context (inbox vs. outbox, received vs. constructed) determines meaning.
   - **Recommendation**: Always qualify as "inbound **Activity**" or "outbound **Activity**" when direction matters.

7. **"Factory" scope** — The term **Factory** can mean:
   - The set of **Factory Functions** in the `vultron/wire/as2/factories/` package (the public API)
   - A single **Factory Function** (e.g., `create_report()`)
   - Never use "factory" to mean "the place where activities are made" — always say **Factory Function** or **factories package**.

8. **"Port" (hexagonal vs. TCP)** — In this domain, **Port** always means a hexagonal architecture interface contract, never a TCP port. No TCP concepts are in scope.

9. **"Deprecated" methods** — `get()` and `by_type()` on **DataLayer** are called "deprecated" but still exist in the codebase. This means they are marked for removal and are being gradually replaced by **Narrow Ports** (**CasePersistence**, **CaseOutboxPersistence**) and **Rehydration**. "Deprecated" ≠ "removed yet."

10. **"Narrow" vs. "broad" ports** — A **Narrow Port** is small, typed, domain-specific (e.g., `CasePersistence` with `read_by_id()`, `list_by_status()`). A broad port is generic and untyped (e.g., `DataLayer` with `get(table, id)`, `by_type(type)`). The goal is to replace broad ports with **Narrow Ports** to improve type safety and reduce coupling.

11. **"Report" vs. "Case"**:
    - A **Report** is a one-time vulnerability notification from a **Reporter**.
    - A **Case** is the ongoing coordination container with state machines (RM, EM, CS) and participants.
    - Multiple **Reports** may consolidate into one **Case**; one **Report** may split into multiple **Cases**.
    - **Recommendation**: "Report" = inbound notification; "Case" = coordination entity with state machines.

12. **"Embargo" vs. "Embargo Consent"**:
    - An **Embargo** is a shared agreement (one per **Case**) that all parties will not disclose until a certain date.
    - **Embargo Consent** is each **Participant**'s individual acceptance or rejection of that embargo.
    - **Recommendation**: If discussing terms/dates, say "Embargo"; if discussing one party's stance, say "Embargo Consent".

13. **"Case Owner" vs. "Case Actor" vs. "Case Manager" (role)**:
     - A **Case Owner** is a human **Participant** (e.g., Reporter) with a **CVDRole.CASE_OWNER** value; the decision-maker and administrator of the **Case**.
     - A **Case Actor** is the auto-generated ActivityStreams Service actor created during case initialization; maintains the **canonical recorded log** and coordinates state across participants.
     - **Case Manager** is a **CVDRole** value (not a role delegation; rather a role assignment) held by the service actor that manages case replica synchronization on behalf of the **Case Owner**; always held alongside **COORDINATOR**.
     - **Recommendation**: Use "Case Owner" for the human decision-maker; "Case Actor" or "Case Manager actor" for the service peer; "CASE_MANAGER role" when discussing the role value. Avoid "case manager" as standalone unless context is clear.

14. **"Participant Case Replica" vs. "Case State"**:
     - A **Participant Case Replica** is a local copy of case state on a participant's node; must be seeded via **Trust Bootstrap** and maintain **Eventual Consistency** with the **CaseActor**'s authoritative state.
     - **Case State (CS)** is the formal six-dimensional state model (VfDpxa lattice) tracking vulnerability awareness and readiness.
     - **Recommendation**: Use "Participant Case Replica" for participant-local state copies; "Case State" for the formal model.

15. **"CVDRole" vs. "CVDRolesFlag"**:
     - **CVDRole** is a StrEnum (string enum) representing individual, atomic roles; participants hold zero or more roles as `list[CVDRole]`; this is the **preferred** representation for all new code.
     - **CVDRolesFlag** is a legacy Flag enum (bitmask) used only by the `vultron.bt` simulator layer; it existed before the migration to list-based roles and is retained for backward compatibility only.
     - **Recommendation**: Always use `list[CVDRole]` in new code; never use **CVDRolesFlag** outside the `vultron.bt` simulator. When discussing roles, say "CVDRole" or "role list," never "CVDRoles" (plural, deprecated name).

---

---

## Example Dialogues

### Formal Protocol Structure Example

> **Protocol Designer:** "OK, so in the formal model, we have N processes. What exactly is a process?"
>
> **Formal Spec Expert:** "Each **Participant** in a **Case** runs one **Process**. A **Process** maintains a **Composite State** — that's a 3-tuple: (**Case State**, **RM State**, **EM State**)."
>
> **Protocol Designer:** "So if a **Vendor** is in the case, they're one **Process**?"
>
> **Formal Spec Expert:** "Exactly. The **Vendor** runs their own RM state machine, tracks the shared EM state, and maintains their part of the **Case State** (**Vendor Fix Path**). Meanwhile, a **Coordinator** in the same **Case** is another **Process** with their own RM state and the same EM state."
>
> **Protocol Designer:** "And they coordinate through **Message Types**?"
>
> **Formal Spec Expert:** "Yes. When a **Vendor** transitions their RM from Valid to Accepted, they send an **RA** (Report Accepted) **Message Type**. That **Activity** carries the **RA** and is transmitted via the wire protocol. The **Coordinator** receives it and updates their model of the **Vendor**'s **RM State**."
>
> **Protocol Designer:** "But that doesn't change the **Coordinator**'s own RM state?"
>
> **Formal Spec Expert:** "Correct. The **RA** message is an announcement — 'I accepted the report.' It doesn't command the receiver to do anything. Only **Report Submission (RS)** directly changes receiver RM state."
>
> **Protocol Designer:** "What about **CS Events** — if the **Vendor** completes a fix, do they have to send a message?"
>
> **Formal Spec Expert:** "Not technically. The **Vendor** internal transitions from Vfd to VFd is a **CS Event** (F). But per the protocol, they SHOULD announce it by sending a **CF (Fix Readiness)** message. However, the message and the state transition are distinct — one doesn't require the other formally."

### Architecture Example

> **Architect:** "OK, so our issue is that `vultron/core/use_cases/triggers/sync.py` calls
> `from_core()` — but `from_core()` is in the wire layer. That violates ARCH-03-001."
>
> **Developer:** "Right, I see it: `CaseLogEntry.from_core(entry)`. Why can't the core just call
> that?"
>
> **Architect:** "Because core has no imports from wire. The solution is TASK-AF: we create
> **Factory Functions** in `vultron/wire/as2/factories/`. Then instead of core calling `from_core()`,
> we have a driven **Port** — an **Activity Translator** adapter — that core calls with a domain
> object, and the adapter uses the **Factory Function** to build the wire **Activity**."
>
> **Developer:** "So the **Factory Function** is in wire, and core doesn't see it?"
>
> **Architect:** "Exactly. Core only knows about the **Port** interface. The adapter implements it,
> and the adapter has the wire imports. Core stays clean."
>
> **Developer:** "Got it. And once TASK-AF lands, we can fix the hexagonal violations in sync.py?"
>
> **Architect:** "Yes — that's TASK-ARCHVIO. After **Factory Functions** exist, we introduce the
> **Activity Translator Port** and move `from_core()` calls from core to the adapter. Then
> ARCH-03-001 is satisfied."
>
> **Developer:** "And what about TASK-CP-CLEANUP? That's about removing `get()` and `by_type()`,
> right?"
>
> **Architect:** "Yes. Currently core uses the broad **DataLayer Port** and calls `get(table, id)`.
> We want core to use **Narrow Ports** like **CasePersistence** with typed methods like
> `read_by_id()`. Once all 64 call sites migrate, we remove the old **Compatibility Methods**."

### CVD Domain Example

> **Protocol Designer:** "When a **Vendor** receives a **Report**, do they immediately become a
> **Participant** in the **Case**?"
>
> **Domain Expert:** "Not automatically. A **Report** is created by a **Reporter** and assigned to a
> **Case**. The **Vendor** becomes a **Participant** only after the **Case Owner** sends an **Offer
> Activity** and the **Vendor** sends an **Accept Activity**. Until then, the **Vendor** is invited
> but not yet participating."
>
> **Protocol Designer:** "So if a **Vendor** doesn't respond to the **Offer**, they don't show up in
> the **Case** participant list?"
>
> **Domain Expert:** "Correct. The **Case** tracks only actual **Participants**. An unresponded
> **Offer** is a protocol event we record, but it doesn't create a **Participant**."
>
> **Protocol Designer:** "What happens to the RM state if a **Vendor** joins the **Case** late—after
> we've already transitioned to PUBLISHED?"
>
> **Domain Expert:** "Their **Participant Status** records RM states from the point they joined onward.
> They won't have history for earlier states, but their RM state machine can still advance through
> valid transitions. The **Case Status** is separate—it shows the collective state across all
> parties."
>
> **Protocol Designer:** "And when we send an **Activity** about a **State Transition** to all
> participants, we're not telling them to do the transition—we're informing them that we did it?"
>
> **Domain Expert:** "Exactly. An **Activity** is a state-change notification, not a command. If I
> send you an **Activity** saying 'Fix Deployed' (the **D** event), I'm informing you that my
> organization deployed the fix. You update your model of the **Case State** and potentially make your
> own decisions based on that new information."

---

## Metadata

- **Source:** Vultron codebase, CERT/CC CVD research publications, architecture audit, formal protocol specification
- **Last Updated:** 2026-05-08
- **Domains:** Formal MPCVD protocol, CVD process models (RM/EM/CS), communicating state machines, hexagonal architecture, activity pattern matching, persistence abstraction, behavior tree orchestration, case actor federation, participant case replicas, trust bootstrap and delegation
- **Related References:**
  - [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513) (CMU/SEI-2021-SR-021)
  - [Designing Vultron: A Protocol for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=887198)
  - CERT Guide to Coordinated Vulnerability Disclosure (v2.0)
  - `docs/topics/process_models/` — detailed RM, EM, CS models
  - `docs/reference/formal_protocol/` — formal protocol specification
  - `notes/case-bootstrap-trust.md` — trust bootstrap and delegation design
  - `notes/case-creation-sequence.md` — case creation and participant initialization
  - `specs/participant-case-replica.yaml` — PCR safety rules and eventual consistency
