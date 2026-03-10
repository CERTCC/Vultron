# Use Cases, Domain Logic, and Behavior Trees

This note clarifies the relationship between **use cases**, **domain logic**,
and **behavior trees**, and proposes a module layout for organizing them.

The goal is to keep:

* orchestration logic simple
* domain rules centralized
* behavior policies explicit and testable

---

# Conceptual Layering

The system should follow this execution flow:

```
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

# What a Use Case Is

A **use case** represents an actor goal or system capability.

Examples:

```
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

# Why Use Cases Sit Above Behavior Trees

Use cases represent **external intentions**, while behavior trees represent *
*internal policy decisions**.

Example:

```
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

```
Use Case
    triggers
Behavior Tree
```

This separation ensures:

* policy logic is centralized
* use cases remain simple
* behavior can evolve without changing entry points

---

# Behavior Trees

Behavior trees implement domain policies.

Example tree:

```
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

# Event-Driven Behavior

Behavior trees may also react to **domain events**.

Example:

```
InvitationAccepted
    → ParticipantOnboardingTree
```

Event-driven execution loop:

```
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

# Suggested Directory Layout

Example structure:

```
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

# Mapping Protocol Activities

Protocol activities should map cleanly to use cases.

Example:

```
Invite → InviteActorToEmbargo
Accept → AcceptEmbargoInvitation
Publish → PublishAdvisory
```

Use cases then invoke the appropriate behavior trees.

This keeps protocol concerns separate from domain behavior.

---

# Design Goals

This structure provides:

* clear separation of orchestration and policy
* explicit domain behavior
* easier testing of policy logic
* support for event-driven coordination

The system becomes:

```
protocol event
    → use case
    → behavior tree
    → domain state change
    → domain events
```

This model is well-suited to **federated coordination systems** where many
independent actors interact through shared protocol events.
