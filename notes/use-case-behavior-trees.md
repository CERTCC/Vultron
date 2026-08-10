---
title: Use Cases, Domain Logic, and Behavior Trees
status: active
description: >
  Clarifies the relationship between use cases, domain logic, and behavior
  trees; documents where each concern belongs.
related_specs:
  - specs/code-style.yaml
  - specs/bt-composability.yaml
related_notes:
  - notes/bt-integration.md
  - notes/domain-model-separation.md
relevant_packages:
  - transitions
  - vultron/core/use_cases
  - vultron/core/behaviors
---

# Use Cases, Domain Logic, and Behavior Trees

This note clarifies the relationship between **use cases**, **domain logic**,
and **behavior trees**, and documents the canonical reference model connecting
use-case BTs to the full CVD protocol BT.

The goal is to keep:

* orchestration logic simple
* domain rules centralized in the behavior tree
* behavior policies explicit, inspectable, and auditable

---

## Core Principle: The Tree Is the Documentation

The behavior tree IS the domain documentation. If a protocol-observable
action — emitting an activity, transitioning RM/EM/CS state, creating a
domain object, cascading to a downstream behavior — is not implemented as a
BT node or subtree, it is **invisible to analysis, audit, and explainability
tools**.

This is not a style preference. It is the design invariant that makes
Vultron's process inspectable without reading implementation code. The
enforceable form of this invariant is `BTC-03-001` in
`specs/bt-composability.yaml`.

### Procedural Glue vs. Domain Logic

The `execute()` method of a use case MAY contain infrastructure glue only:

* Instantiate the BT
* Set up the blackboard from the event (load actor/case IDs, etc.)
* Call `bridge.execute_with_setup()` (or `bt.run()`)
* Check the BT status
* Extract output from the blackboard

**Nothing else domain-significant lives outside the tree.**

### Anti-Pattern (MUST NOT)

```python
class SvcValidateReportUseCase:
    def execute(self) -> HandlerResult:  # UCORG-05-001: must return UseCaseResult subtype
        # ... setup ...
        bridge.execute_with_setup(self._dl, bt, bb)   # BT runs

        # ❌ ANTI-PATTERN: domain action outside the tree
        if bt.status == Status.SUCCESS:
            SvcEngageCaseUseCase(self._dl, engage_event).execute()
        return HandlerResult()
```

The call to `SvcEngageCaseUseCase` after the BT runs means the
validate→engage cascade is invisible at the BT level. It cannot be audited
from the tree structure alone.

### Correct Pattern (BT Subtree Cascade)

```python
class SvcValidateReportUseCase:
    def execute(self) -> HandlerResult:  # UCORG-05-001: must return UseCaseResult subtype
        # ... setup ...
        bt = ValidateReportBt(...)   # ← includes PrioritizeBt as a child
        bridge.execute_with_setup(self._dl, bt, bb)   # ✅ cascade inside tree
        # check status, extract output only
        return HandlerResult()
```

The validate→engage/defer cascade is a child subtree of `ValidateReportBt`,
mirroring the canonical CVD protocol BT structure.

---

## Trunk-Removed Branches Model

The per-use-case BT model is not a deviation from the canonical BT — it
removes the top-level continuous-tick trunk and exposes individual
subbranches as use cases triggered by external events (HTTP inbox, trigger
API, CLI). The branch structure remains intact.

See `notes/bt-integration.md` for:

* The full trunk-removed branches model
* A mapping table: canonical subtree path → current use case
* Implementation guidance for locating where a new behavior belongs in the
  canonical tree before implementing it
* The prioritize subtree detail (validate → engage/defer)

### Why This Matters

The canonical BT defines the normative CVD process. Use-case BTs that
deviate from it without justification create a gap between the documented
process and the implemented one. That gap breaks explainability.

**Rule**: Every use-case BT MUST correspond to an identifiable subtree of the
canonical CVD protocol BT. Divergences MUST be documented (in a note or ADR)
with justification.

---

## Conceptual Layering

The system should follow this execution flow:

```text
Driver (HTTP / CLI / protocol)
        ↓
Dispatcher
        ↓
Use Case
        ↓
Behavior Tree
        ↓
Domain Model
        ↓
Domain Events
```

Responsibilities of each layer:

| Layer         | Responsibility                              |
|---------------|---------------------------------------------|
| Driver        | Accept external input (protocol, CLI, HTTP) |
| Dispatcher    | Map protocol events to use cases            |
| Use Case      | Orchestrate a single actor goal             |
| Behavior Tree | Evaluate domain policy and decide actions   |
| Domain Model  | Maintain state and enforce invariants       |
| Domain Events | Record meaningful state transitions         |

---

## What a Use Case Is

A **use case** represents an actor goal or system capability.

Examples:

```text
AddParticipantToCase
InviteActorToEmbargo
AcceptEmbargoInvitation
PublishAdvisory
```

Use cases should be **thin orchestration layers**.

Typical structure:

```python
class InviteActorToEmbargo:

    def execute(self, activity):
        case = repo.load(activity.case_id)

        tree = EmbargoInviteTree(case)

        tree.run(activity)

        repo.save(case)
```

A use case should:

* load aggregates
* invoke behavior logic
* persist results
* emit domain events

A use case should **not contain complex business rules**.

---

## Why Use Cases Sit Above Behavior Trees

Use cases represent **external intentions**, while behavior trees represent *
*internal policy decisions**.

Example:

```text
Actor goal:
    Invite participant

System decisions:
    Is the case open?
    Is the actor trusted?
    Is the invitation duplicate?
    Should other participants be notified?
```

Those decisions belong in behavior trees.

Therefore:

```text
Use Case
    triggers
Behavior Tree
```

This separation ensures:

* policy logic is centralized
* use cases remain simple
* behavior can evolve without changing entry points

---

## Behavior Trees

Behavior trees implement domain policies.

Example tree:

```text
EmbargoInviteTree

Selector
 ├─ AlreadyInvited
 ├─ CaseClosed
 └─ AcceptInvite
        ├─ AddInvitation
        ├─ RecordAuditEvent
        └─ NotifyParticipants
```

Nodes should only:

* inspect domain state
* modify domain state
* emit domain events

Nodes must **not perform infrastructure work**.

---

## Event-Driven Behavior

Behavior trees may also react to **domain events**.

Example:

```text
InvitationAccepted
    → ParticipantOnboardingTree
```

Event-driven execution loop:

```text
Domain Event
      ↓
Behavior Engine
      ↓
Run trees subscribed to event
      ↓
Modify domain state
      ↓
Emit new events
```

This allows coordination workflows to emerge from events rather than hard-coded
handlers.

---

## Suggested Directory Layout

Example structure:

```text
core/

  domain/
      vulnerability_case.py
      embargo.py

  events/
      domain_events.py

  behavior/

      engine.py
      registry.py

      trees/
          embargo_invite_tree.py
          embargo_accept_tree.py
          publish_advisory_tree.py

      nodes/
          check_case_open.py
          check_duplicate_invite.py
          add_invitation.py
          notify_participants.py

application/

  use_cases/
      invite_actor_to_embargo.py
      accept_embargo_invitation.py
      publish_advisory.py
```

Guidelines:

* **domain/** contains aggregates and invariants
* **behavior/** contains policy logic
* **application/use_cases/** contains orchestration

---

## Mapping Protocol Activities

Protocol activities should map cleanly to use cases.

Example:

```text
Invite → InviteActorToEmbargo
Accept → AcceptEmbargoInvitation
Publish → PublishAdvisory
```

Use cases then invoke the appropriate behavior trees.

This keeps protocol concerns separate from domain behavior.

---

## Design Goals

This structure provides:

* clear separation of orchestration and policy
* explicit domain behavior
* easier testing of policy logic
* support for event-driven coordination

The system becomes:

```text
protocol event
    → use case
    → behavior tree
    → domain state change
    → domain events
```

This model is well-suited to **federated coordination systems** where many
independent actors interact through shared protocol events.

---

## Standardized Use Case Interface

### Problem

Use cases in `core/use_cases/` are currently standalone functions with
heterogeneous signatures. Each adapter must know the exact calling convention
for every function, creating tight coupling and complicating future
extensibility.

### Proposed Protocol

Define a generic `UseCase` protocol with explicit request and response types:

```python
from typing import Protocol, TypeVar

Req = TypeVar("Req")
Res = TypeVar("Res")


class UseCase(Protocol[Req, Res]):
    def execute(self, request: Req) -> Res: ...
```

Each use case:

* accepts **exactly one request object** (a Pydantic model)
* returns **exactly one response object** (a Pydantic model)
* implements an `execute()` method

### Rationale

* **Consistent invocation** — all adapters call use cases the same way.
* **Loose coupling** — adapters depend on the protocol, not individual
  function signatures.
* **Stable evolution** — request/response objects allow fields to evolve
  without breaking adapters.
* **Clear boundary** — `execute()` is the explicit entry point into core.
* **Tooling compatibility** — structured request objects are easier to
  serialize, validate, log, or expose to agent/tool interfaces.

### Important Ordering Note

The use-case interface standardization SHOULD be implemented **before**
P75-4 (refactoring driving adapters to call use cases directly). A
consistent `execute()` interface makes P75-4 significantly simpler.

### Use Case Naming Convention

Handler use cases (processing incoming messages from another party) SHOULD carry
a `Received` suffix: `CreateReportReceivedUseCase`. Trigger use cases
(actor-initiated actions) SHOULD carry a `Svc` prefix: `SvcEngageCaseUseCase`.
This mirrors the `FooReceivedEvent` / `FooTriggerEvent` convention for domain
events (CS-10-002) and makes the origin unambiguous at a glance. See
`specs/code-style.yaml` CS-12-002 and TECHDEBT-21.

### UseCaseRequest Envelope (Evaluated and Rejected — see ADR-0040)

`UseCaseRequest` was evaluated during the planning of issue #423 and
**rejected**. The core finding: `VultronEvent` and `TriggerRequest` share the
field name `actor_id` but carry it in semantically opposite roles — one
represents inbound remote actor identity, the other represents local outbound
intent. Merging them under a shared base collapses a security boundary.

See `docs/adr/0040-use-case-result-envelope.md` for the full decision
rationale and `notes/use-case-protocol.md` for implementation guidance on the
`UseCaseResult` hierarchy that was introduced instead.

### SEMANTICS_HANDLERS Migration

`SEMANTICS_HANDLERS` in `vultron/api/v2/backend/handler_map.py` maps
`MessageSemantics` values (domain concepts) to handler callables (domain
code). Because this mapping is domain knowledge, it belongs in
`core/use_cases/use_case_map.py`, not in the adapter layer. This migration
should happen as part of P75-2c.

**See**: `notes/domain-model-separation.md` "Post-P75-2 Architecture
Findings" for additional context.
