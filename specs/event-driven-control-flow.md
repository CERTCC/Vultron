# Event-Driven Control Flow Specification

## Overview

This specification defines the event-driven processing model for Vultron
actors: how primary events enter the system, how cascading consequences are
produced automatically, and what constraints apply to demo scripts and
integration tests.

**Source**: IDEA-26041701 (Clarification of intended control flow)

**See also**: `specs/behavior-tree-integration.md` (BT cascade mechanism),
`specs/outbox.md` (outbox delivery), `notes/event-driven-control-flow.md`
(conceptual actor model and design rationale),
`notes/protocol-event-cascades.md` (concrete cascade gap inventory)

---

## Definitions

- `EDF-01-001` A **primary event** is an externally supplied stimulus or an
  actor-initiated decision: a message delivered to an actor's inbox, or a
  trigger invocation representing an actor choosing to begin an action.
  - Primary events are the only events that demos, human operators, or
    agentic clients MUST supply directly.
- `EDF-01-002` A **cascade** is an automatic, BT-driven consequence that
  occurs within a single actor's execution context as a result of processing
  a primary event or an earlier cascade step.
  - Cascades are scoped to one actor; they MUST NOT depend on external
    callers to initiate them.
- `EDF-01-003` A **cascade chain** is the full sequence of causally connected
  steps that flows from one primary event: within-actor cascade → outbox
  emission → delivery to peer inbox → peer's own cascade → and so on.
- `EDF-01-004` An **external decision node** is a BT node that cannot
  complete autonomously: it requires input from an actor, a user interface,
  or an external system before it can return `SUCCESS` or `FAILURE`.
  - An external decision node MUST return `RUNNING` until the required input
    arrives.
  - External decision nodes are the **only** legitimate stopping points in a
    cascade chain; all other cascade steps MUST complete automatically.

---

## Event-Driven Processing

- `EDF-02-001` Every protocol-significant action in Vultron MUST be triggered
  by an event, not by direct procedural calls from upstream code.
- `EDF-02-002` The system MUST follow an "on event, do" model: business logic
  is invoked in response to events; events are not invoked by business logic.
- `EDF-02-003` The inbox MUST be the sole entry point for inbound activity
  processing; handlers MUST NOT be invoked directly by callers that bypass
  the inbox dispatch pipeline.
- `EDF-02-004` The outbox MUST be the sole exit point for outbound activity
  delivery; handlers MUST NOT deliver activities directly to peer actors.

---

## Cascade Implementation

- `EDF-03-001` All cascade steps that do not require external input MUST be
  implemented as BT subtrees within the handling actor's BT execution context.
  - See `specs/behavior-tree-integration.md` BT-06-001 through BT-06-006.
- `EDF-03-002` Outbox emissions that are part of a cascade MUST be implemented
  as BT leaf-node actions (e.g., `EmitXxxNode`); they MUST NOT be procedural
  calls made after `BTBridge.execute_with_setup()` returns.
- `EDF-03-003` A use case's `execute()` method MUST contain only
  infrastructure glue: BT instantiation, blackboard setup, bridge execution,
  status check, and output extraction.
  - Domain logic and cascade steps MUST NOT appear outside the BT.
- `EDF-03-004` The cascading consequence of a primary event MUST be
  fully determined by BT execution with no required intermediate trigger
  steps, except at explicit external decision nodes (see EDF-04).
- `EDF-03-005` Cascade logic MUST NOT be duplicated between actors; each
  actor's BT handles its own local cascade, triggered by receipt of the peer's
  outgoing activity.

---

## External Decision Nodes

- `EDF-04-001` When a cascade reaches a point where the actor cannot proceed
  autonomously, the stopping point MUST be represented as an explicit external
  decision node in the BT.
- `EDF-04-002` An external decision node MUST return `py_trees.common.Status.RUNNING`
  while awaiting input; it MUST NOT silently succeed or fail, and MUST NOT be
  modeled as an absence of code.
- `EDF-04-003` The arrival of the required external input (a trigger
  invocation, an inbox message, or a UI response) MUST cause the external
  decision node to re-evaluate and return `SUCCESS` or `FAILURE` on the next
  BT tick.
- `EDF-04-004` Trigger endpoints that correspond to external decision node
  resolutions MUST be documented as such; their role is to supply the
  missing input, not to choreograph a cascade that should be automatic.

---

## Demo Constraints

- `EDF-05-001` Demo scripts MUST inject only primary events into the system.
- `EDF-05-002` Demo scripts MUST NOT trigger intermediate cascade steps
  manually; all cascade steps that are not external decision nodes MUST
  complete automatically as a result of the primary event.
- `EDF-05-003` Demo scripts MUST verify correctness by observing externally
  visible system state (e.g., DataLayer contents, activities queued in the
  outbox) after the primary event and its cascades have settled.
- `EDF-05-004` Demo scripts MUST NOT assert on internal BT execution state
  (e.g., node status, blackboard values) as a substitute for observing
  external system state.
- `EDF-05-005` A demo that must manually trigger intermediate steps to reach
  its expected final state SHOULD be treated as evidence of a cascade
  automation gap that requires a BT fix, not as correct demo behavior.
