---
status: accepted
date: 2026-02-05
deciders:
  - vultron maintainers
consulted:
  - project stakeholders
informed:
  - contributors
---

# Introduce a Behavior Dispatcher Between Inbox Handling and Behavior Execution

## Context and Problem Statement

Vultron actors are implemented as ActivityPub actors with inboxes and outboxes. Inbound messages are ActivityStreams objects, typically Activities that include domain-specific objects (e.g., Vulnerability Reports).

Early prototypes implemented inbound message handling using a layered routing model:

- Inbox handler
- Activity-type handler
- Object-type handler
- Downstream “work” execution

This approach introduced several problems:

- Loss of semantic cohesion: separating activity handling from object handling discarded context required to determine correct behavior; downstream workers had to reconstruct state already known at receipt time.
- Poor alignment with existing behavior logic: Vultron already defines message types as (Activity Type, Object Type) tuples, with corresponding behavior trees defined in the protocol simulator. The routing model obscured this mapping.
- Tight coupling of protocol handling and execution: the inbox handler effectively controlled execution flow, making asynchronous or distributed execution difficult.
- Deployment inflexibility: the design did not cleanly support both local development (“git clone + docker-compose up”) and integration into environments with job queues or workers.

These issues indicated a missing architectural boundary between protocol handling and behavior execution.

## Decision Drivers

- Preserve semantic context when invoking behavior
- Align runtime execution with existing message-type semantics
- Support both simple local deployments and scalable asynchronous architectures
- Improve testability and separation of concerns

## Considered Options

- Keep layered routing inside the inbox handler (current approach)
- Introduce a Behavior Dispatcher abstraction between inbox and behavior execution
- Mandate a specific queuing/pubsub system for dispatching (rejected as non-goal)

## Decision Outcome

Chosen option: "Introduce a Behavior Dispatcher abstraction between inbox handling and behavior execution."

Justification:

- Restores a clear execution boundary that preserves semantics determined at receipt time.
- Keeps behavior trees message-type-specific and implementation-agnostic with respect to invocation mechanics.
- Enables multiple implementations (in-process direct invocation or queued/asynchronous invocation), supporting both local development and distributed deployments.

### Consequences

- Good:
  - Removes redundant activity/object routing layers
  - Preserves semantic context at behavior invocation time
  - Aligns runtime execution with existing Vultron message-type semantics
  - Enables both synchronous and asynchronous execution models
  - Supports both local development and scalable deployments
  - Improves testability by isolating behavior trees
- Bad / Tradeoffs:
  - Introduces an additional abstraction layer
  - Requires explicit dispatcher interface definition and implementations
  - Asynchronous implementations require explicit failure and retry semantics
  - Persistence ordering (write-on-receipt vs behavior-owned writes) must be chosen deliberately

## Validation

- Code and API reviews of dispatcher interface and implementations
- Unit and integration tests exercising both direct and queued dispatcher implementations
- End-to-end tests in local and queued deployment scenarios to validate preservation of message-type semantics and observable behavior

## Pros and Cons of the Options

### Keep layered routing inside inbox handler

- Good: minimal initial change; behavior executes immediately
- Bad: loses semantic context, couples protocol handling and execution, reduces deployment flexibility and testability

### Introduce Behavior Dispatcher (chosen)

- Good: separates concerns, preserves context, supports multiple execution models, improves testability
- Bad: adds an interface and implementation work; requires decisions on persistence semantics for some flows

### Mandate a specific queue/pubsub system

- Good: can simplify an asynchronous reference implementation
- Bad: violates non-goals by specifying infrastructure; reduces portability and increases coupling

## Non-Goals

- This ADR does not specify a particular queue, pub/sub system, or infrastructure provider.
- This ADR does not define federation or delivery mechanics between actors.
- This ADR does not mandate a specific persistence strategy.

## More Information

- This ADR reframes the original design impasse as a missing execution boundary rather than a protocol or domain modeling issue. The Behavior Dispatcher serves as that boundary, allowing Vultron’s protocol-facing components and behavior logic to evolve independently.
- Related ADRs: refer to docs/adr for other architectural records and the ADR template at docs/adr/_adr-template.md.
