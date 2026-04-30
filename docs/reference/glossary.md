# Ubiquitous Language — Priority 473 Architecture

Domain terminology for Vultron architecture hardening (Priority 473) extracted from implementation plan and task audit.

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

---

## Example Dialogue

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

---

## Metadata

- **Source:** Priority 473 task audit + implementation plan
- **Last Updated:** 2026-04-30
- **Domains:** Hexagonal architecture, activity pattern matching, persistence abstraction, behavior tree orchestration
