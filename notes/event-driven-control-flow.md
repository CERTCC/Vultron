---
title: Event-Driven Control Flow Design Notes
status: active
description: >
  Conceptual model for event-driven control flow in Vultron; actor reaction
  patterns and design rationale.
related_specs:
  - specs/event-driven-control-flow.md
related_notes:
  - notes/bt-integration.md
  - notes/bt-reusability.md
  - notes/protocol-event-cascades.md
---

# Event-Driven Control Flow Design Notes

## Overview

Vultron is designed as an event-driven system: actors react to events by
running behaviors, which may emit further events to other actors. This file
captures the conceptual model behind that design, the rationale for key
decisions, and guidance for understanding where the system should (and should
not) do work automatically.

**Formal requirements**: `specs/event-driven-control-flow.md` (EDF-01
through EDF-05)

**Related notes**: `notes/protocol-event-cascades.md` (concrete cascade gap
inventory and fix guidance), `notes/bt-integration.md` (BT design decisions),
`notes/bt-reusability.md` (composable subtree patterns)

---

## Conceptual Actor Model

### Actors as Workers on a Message Queue

The cleanest mental model for understanding how Vultron actors behave is to
think of each actor as a **worker consuming from a message queue**:

- The **inbox** is the actor's inbound queue.
- The **outbox** is the actor's outbound queue.
- The actor's **behavior trees** are the processing logic that runs when a
  message is dequeued.
- A BT that emits an outgoing activity is placing a message on the outbound
  queue, which the outbox handler delivers to peer actors' inboxes.

Under this model, the system's processing loop looks conceptually like:

```text
while running:
    event = inbox.dequeue()              # receive a message
    cascade = bt.run(event)              # run behaviors
    for msg in cascade.emitted:          # emit consequences
        outbox.enqueue(msg)
```

Peer actors receive the emitted messages in their own inboxes and run their
own BTs in response, potentially emitting further messages — forming the
full **cascade chain** described in `specs/event-driven-control-flow.md`
EDF-01-003.

### This Is a Conceptual Model, Not an Implementation Requirement

**Important**: This queue/worker framing is a reasoning tool, not an
implementation blueprint. The current Vultron prototype is a single-process
system. It does not use message brokers, task queues, or distributed workers.
Do not interpret this model as a requirement to introduce RabbitMQ, Celery,
NATS, Kafka, or any other message broker infrastructure into the prototype.

The value of this mental model is that it makes the *intended flow* of
information clear, helps identify violations (places where upstream code is
directly controlling downstream behavior), and ensures the prototype's
architecture remains compatible with a future distributed implementation
should one ever be built.

A future production implementation *could* map directly onto this model —
with a message broker for inboxes/outboxes, separate worker processes per
actor, and BT execution within each worker. The current prototype preserves
that optionality by not introducing tight coupling between the actor logic and
the HTTP/FastAPI delivery mechanism.

---

## Primary Events vs. Cascades

### What Is a Primary Event?

A primary event is an externally supplied stimulus that the protocol requires
an actor to respond to. Primary events are the *only* things that demos, human
operators, or agentic clients need to supply. Examples:

- A finder submitting a vulnerability report (`RmSubmitReportActivity`)
- An actor proposing an embargo (`EmProposeEmbargoActivity`)
- A coordinator inviting a new participant to a case

### What Is a Cascade?

A cascade is everything that follows a primary event *within one actor's
processing context*. The actor's BT runs, checks preconditions, updates local
state, and emits follow-on messages. Cascades should be invisible to the
demo — they happen automatically as the BT executes.

The cascade may end with an outbox emission that delivers a message to a peer.
The peer then processes that message through its own BT — a separate cascade,
scoped to the peer actor. This is how complex multi-actor behaviors emerge
from a single primary event.

### The Correct Mental Test for Demo Design

When writing a demo, ask: *"If I were observing a real deployment of Vultron
from the outside, which events would I need to inject to start this protocol
flow?"* Those are the primary events. Everything else should happen
automatically. If the demo must manually inject an intermediate step, that is
a signal that a cascade is not yet automated — a gap to fix, not a demo
pattern to copy.

---

## External Decision Nodes

### What They Are

An external decision node is a point in a cascade where the BT cannot proceed
autonomously. The actor needs information it does not have — a human judgment
call, a policy decision, or data from an external system — before it can
determine the next step.

In the original Vultron BT simulation (`vultron/bt/`), these points are
represented as **fuzzer nodes** — nodes that return a random success or
failure to simulate the uncertain outcome of a real-world decision. The PRNG
roll stands in for the actual information the actor would need.

In the prototype, external decision nodes are placeholders that return
`RUNNING` until the required input arrives via a trigger endpoint or inbox
message.

### Candidates for Future Automation

External decision nodes are the natural seam for integrating richer
decision-making into Vultron actors. They represent places where:

1. **A UI interaction is appropriate** — the actor presents the case context
   to a human and waits for their choice (e.g., "Accept or reject this
   suggestion to invite Vendor B?").

2. **A narrowly scoped LLM agent is appropriate** — the actor provides a
   structured case summary and a specific question to an LLM agent, which
   returns a structured decision (e.g., "Given these embargo terms, should
   this actor accept or counter-propose?").

This makes external decision nodes the primary extension point for building
progressively more autonomous CVD actors without changing the BT structure —
only the *implementation* of the decision node changes.

### What They Are Not

External decision nodes are NOT:

- An excuse to implement cascade steps procedurally outside the BT
- A place where demos manually bridge two behaviors that should be
  automatically connected
- A substitute for building out a cascade that is deterministic and should
  run automatically

If a cascade step is deterministic (the actor always takes the same action
given the same inputs), it is NOT an external decision node — it is a cascade
step that should be automated.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Cascade scope | Always within a single actor | Simplifies reasoning; each actor owns its own state machine |
| Cascade mechanism | BT subtrees only | BT structure is the auditable, explainable record of what happened |
| Outbox emissions | BT leaf-node actions | Keeps the full causal chain visible in the tree |
| External stops | Explicit `RUNNING` nodes | Absence of code is invisible; explicit nodes document the intent |
| Demo role | Inject primary events + verify state | Demos prove protocol correctness, not API accessibility |
| Queue/worker model | Conceptual only (no broker) | Preserves future optionality without over-engineering the prototype |

---

## Anti-Patterns

### Post-BT Procedural Cascade

```python
# ❌ WRONG — cascade is invisible outside the tree
def execute(self) -> None:
    bridge.execute_with_setup(dl, bt, blackboard)
    self._auto_cascade(...)  # domain logic AFTER BT
```

```python
# ✅ CORRECT — cascade is a child subtree
class ValidateReportBT:
    def setup(self):
        prioritize = create_prioritize_subtree(...)
        self.root.add_child(prioritize)  # inside the tree
```

### Demo Manual Chaining

```python
# ❌ WRONG — demo is doing cascade work
post_to_inbox_and_wait(client, vendor_id, validate_activity)
post_to_inbox_and_wait(client, vendor_id, create_case_activity)  # should be automatic
post_to_inbox_and_wait(client, vendor_id, add_participant_activity)  # should be automatic
```

```python
# ✅ CORRECT — demo injects primary event, verifies outcome
post_to_inbox_and_wait(client, vendor_id, validate_activity)
# ... wait for settlement ...
assert_case_exists_in_datalayer(dl, case_id)  # observe state, not steps
assert_participant_added(dl, case_id, finder_id)
```

### Missing External Decision Node

```python
# ❌ WRONG — BT does nothing, cascade never fires, no signal of why
class SuggestActorReceivedUseCase:
    def execute(self) -> None:
        _idempotent_create(self._request)
        # (silence — no BT, no explanation of why no cascade)
```

```python
# ✅ CORRECT — BT runs, external decision node pauses for owner input
class SuggestActorReceivedUseCase:
    def execute(self) -> None:
        _idempotent_create(self._request)
        tree = create_suggest_actor_tree(...)
        bridge.execute_with_setup(tree, actor_id=case_owner_id)
        # tree contains AwaitCaseOwnerDecisionNode that returns RUNNING
        # until the owner responds via trigger or inbox
```
