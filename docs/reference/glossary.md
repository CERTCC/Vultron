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
| **Case Owner** | The Actor who creates and administers a Case (typically the party seeking vulnerability coordination) | Case creator, case manager |

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
| **Report Management (RM)** | State machine tracking a Report's lifecycle: START → RECEIVED → ACCEPTED → PUBLISHED → CLOSED, with branching to invalid or closed states | Report workflow |
| **Embargo Management (EM)** | State machine tracking an Embargo's lifecycle: NONE → PROPOSED → ACCEPTED → APPROVED (active) → EXPIRED or REVOKED | Embargo workflow |
| **Case Status** | A snapshot of RM, EM, and CS state at a specific moment, with a timestamp and attribution | State record |
| **Participant Status** | A snapshot of a Participant's RM state and embargo consent, recording their role and commitment at a specific moment | Status record |
| **State Transition** | A move from one valid state to another in the RM, EM, or CS machine; always forward (events cannot be undone) | State change, event |

---

## Embargo and Timing

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Embargo** | A time-bounded agreement that participating parties will not publicly disclose a vulnerability until a specific date or condition is met | NDA, disclosure delay, embargo period |
| **Embargo Event** | A point-in-time record of an embargo's end date, context, and who initiated it; used to track embargo history | Embargo record |
| **Embargo Consent** | A Participant's agreement to or rejection of a proposed Embargo (a personal commitment, distinct from the Embargo itself) | Embargo acceptance, embargo stance |
| **Active Embargo** | The currently in-force Embargo for a Case; there is at most one | Current embargo, ongoing embargo |
| **Proposed Embargo** | An Embargo that has been offered but not yet accepted by all parties | Embargo offer, pending embargo |

---

## Messaging and Protocol

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Semantic Type** (or **MessageSemantics**) | The classification of an Activity's meaning (e.g., `CreateReport`, `AcceptEmbargoOnCase`, `ProposeEmbargo`); determines how it is processed | Activity type, message type |
| **Inbox** | The protocol endpoint where an Actor receives incoming Activities from other parties | Receiver, endpoint |
| **Outbox** | The protocol channel through which an Actor broadcasts Activities to other known parties | Sender, distribution |

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
| **Narrow Port** | A port with a small, typed, domain-specific interface (e.g., `CasePersistence`) versus a broad generic one (e.g., `DataLayer`) | Constrained port, domain port |
| **Driven Port** | A port that exposes an outbound dependency; core calls it to reach adapters (e.g., `DataLayer`, activity translators) | Dependency port |
| **Hexagonal Architecture** | Layered design where core business logic has no imports from wire format, adapter, or external framework layers | Ports and adapters, onion architecture |

## Activity & Wire Format

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Activity** | A Vultron protocol message in ActivityStreams 2.0 JSON format; represents a state change notification (Create, Accept, Reject, etc.) | Message, notification, AS2 object |
| **Inbound Activity** | An **Activity** received at the inbox from a remote actor; must be parsed, pattern-matched, and semantically extracted | Received message |
| **Outbound Activity** | An **Activity** constructed by a use case and queued in an outbox for delivery to remote actors | Sent message, outgoing activity |
| **ActivityPattern** | A template for matching an inbound **Activity** structure; used to extract semantic intent (e.g., a `CreateReport` vs an `AcceptInvite`) | Matcher, pattern, discriminator |
| **Semantic Extraction** | The process of mapping an inbound **Activity** structure to a domain-level **MessageSemantics** enum value | Pattern matching, dispatch, intent detection |
| **MessageSemantics** | A domain-level enum of message intents (e.g., `CREATE_REPORT`, `ACCEPT_INVITE_TO_EMBARGO_ON_CASE`) | Message type, semantic type, intent |
| **Factory Function** | A public, type-safe constructor function that builds outbound **Activities**; ensures validation and returns plain AS2 types | Activity constructor, builder |
| **from_core()** | A wire-layer method that constructs wire objects from domain objects; should only be called from adapters, not core use cases | Wire constructor |

## Persistence & Data Access

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **DataLayer** | A broad, generic persistence port that core modules use to store and retrieve case data; provides raw `dict` access | Persistence, storage, database |
| **CasePersistence** | A narrow, typed persistence port for case-specific queries; replaces broad `get()`/`by_type()` with domain-specific methods like `read_by_id()` and `list_by_status()` | Case DAO, case repository |
| **CaseOutboxPersistence** | A narrow, typed persistence port for outbox (outbound activity queue) queries; separate from case data | Outbox DAO, outbox repository |
| **Rehydration** | The process of deserializing raw persisted records (dicts) into typed domain objects (Pydantic models) | Deserialization, model coercion, casting |
| **Compatibility Method** | A deprecated method (`get()`, `by_type()`) still present for backward compatibility but marked for removal | Escape hatch, legacy method |

## Behavior Trees

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **BT** | A Behavior Tree; a state machine implementation using py_trees that orchestrates domain logic and protocol events | State machine, tree, orchestrator |
| **Node** | A component in a **BT** that extends `Behavior` and implements a single domain action (e.g., create a participant, attach a note) | Action, task |
| **Blackboard** | Global shared state storage for **BT** nodes to read/write data during execution | Shared memory, context |
| **BTTestScenario** | A deep-module test harness that eliminates boilerplate setup; allows BT node tests to be written without repeating blackboard initialization | Test fixture, test helper |

## Domain Model — CVD Coordination

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **CVDRoles** | A Flag enum representing participant roles in Coordinated Vulnerability Disclosure (FINDER, REPORTER, VENDOR, DEPLOYER, COORDINATOR, etc.); stored as bitmask | Role bitmap, role flag |
| **CASE_OWNER** | A new **CVDRoles** flag value (not yet added) that marks a participant as the case owner; distinct from other roles and combinable with them | Owner role |
| **Participant** | A CVD actor in a case; has **CVDRoles**, contact info, and status in the case state machine | Actor, stakeholder |
| **CreateInitialVendorParticipant** | A BT **Node** that adds a hardcoded VENDOR **Participant** during case initialization; demo-specific, to be replaced | InitialParticipantNode |
| **CreateCaseOwnerParticipant** | A generalized BT **Node** (not yet implemented) that reads **CVDRoles** from actor configuration and creates a **Participant** with those roles plus **CASE_OWNER** | Configurable participant node |

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

## Relationships

- A **Port** is implemented by one or more **Adapters**.
- **Inbound Activities** are matched by **ActivityPatterns** to extract **MessageSemantics**.
- **Outbound Activities** are constructed by **Factory Functions** (not by core calling `from_core()`).
- A **TASK** may be blocked by another **TASK** via a **Blocker**.
- A **TASK** contains one or more **Subtasks** with **Acceptance Criteria**.
- **CasePersistence** and **CaseOutboxPersistence** replace the broad **DataLayer** interface for core use cases.
- **Rehydration** converts raw persisted dicts (from **DataLayer**) into typed domain objects.
- A **Participant** has zero or more **CVDRoles** (represented as **CVDRoles** bitmask; will become `list[CVDRoles]` after TASK-BTND5.4).
- A **BT Node** reads from and writes to the **Blackboard** and may emit **Outbound Activities**.

---

## Flagged Ambiguities

1. **"Activity" direction** — The term **Activity** is used for both **Inbound** and **Outbound**. Both
   follow the same ActivityStreams 2.0 format, but the context (inbox vs. outbox, received vs.
   constructed) determines meaning. Recommendation: always qualify as "inbound **Activity**" or
   "outbound **Activity**" when direction matters.

2. **"Factory" scope** — The term **Factory** can mean:
   - The set of **Factory Functions** in the `vultron/wire/as2/factories/` package (the public API)
   - A single **Factory Function** (e.g., `create_report()`)
   - Never use "factory" to mean "the place where activities are made" — always say **Factory
     Function** or **factories package**.

3. **"Port" (hexagonal vs. TCP)** — In this domain, **Port** always means a hexagonal architecture
   interface contract, never a TCP port. No TCP concepts are in scope.

4. **"Deprecated" methods** — `get()` and `by_type()` on **DataLayer** are called "deprecated" but
   still exist in the codebase. This means they are marked for removal and are being gradually
   replaced by **Narrow Ports** (**CasePersistence**, **CaseOutboxPersistence**) and **Rehydration**.
   "Deprecated" ≠ "removed yet."

5. **"Narrow" vs. "broad" ports** — A **Narrow Port** is small, typed, domain-specific (e.g.,
   `CasePersistence` with `read_by_id()`, `list_by_status()`). A broad port is generic and
   untyped (e.g., `DataLayer` with `get(table, id)`, `by_type(type)`). The goal is to replace
   broad ports with **Narrow Ports** to improve type safety and reduce coupling.

6. **"State" (multiple meanings)**:
   - The **Case State (CS)** — the six-dimensional VfDpxa lattice model (64 possible states)
   - A **Case Status** — a snapshot of CS, RM, and EM at one moment
   - An RM or EM state — a specific state machine location
   - **Recommendation**: Use "Case State" for the lattice; "Case Status" for a snapshot; "RM state" or "EM state" for a specific location.

7. **"Participant" vs. "Actor"**:
   - An **Actor** is any URI-identified federated peer (a role in the protocol).
   - A **Participant** is an Actor actively engaged in a specific **Case**.
   - A **Reporter** is both an **Actor** (in general) and might be a **Participant** (in a specific Case).
   - **Recommendation**: Use "Actor" when discussing federation; use "Participant" when discussing a specific Case.

8. **"Report" vs. "Case"**:
   - A **Report** is a one-time vulnerability notification from a **Reporter**.
   - A **Case** is the ongoing coordination container that may span multiple **Reports** (if consolidated) or multiple **Cases** (if split).
   - **Recommendation**: "Report" = inbound vulnerability notification; "Case" = coordination event with state machines and participants.

9. **"Embargo" vs. "Embargo Consent"**:
   - An **Embargo** is a shared agreement (one per **Case**) that all parties will not disclose until a certain date.
   - **Embargo Consent** is each **Participant**'s individual acceptance or rejection of that embargo.
   - **Recommendation**: If discussing terms, say "Embargo"; if discussing one party's stance, say "Embargo Consent".

---

## Example Dialogues

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

- **Source:** Vultron codebase, CERT/CC CVD research publications, architecture audit
- **Last Updated:** 2026-04-30
- **Domains:** CVD protocol, hexagonal architecture, activity pattern matching, persistence abstraction, behavior tree orchestration, state machine design
- **Related References:**
  - [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513) (CMU/SEI-2021-SR-021)
  - [Designing Vultron: A Protocol for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=887198)
  - CERT Guide to Coordinated Vulnerability Disclosure (v2.0)
