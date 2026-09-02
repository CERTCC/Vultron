---
title: Event-Driven Control Flow Design Notes
status: active
description: >
  Conceptual model for event-driven control flow in Vultron; actor reaction
  patterns and design rationale.
related_specs:
  - specs/event-driven-control-flow.yaml
  - specs/multi-actor-demo.yaml
  - specs/demo-ci.yaml
related_notes:
  - notes/bt-integration.md
  - notes/bt-composability.md
  - notes/protocol-event-cascades.md
  - notes/demo-ci-diagnostics.md
  - notes/demo-scenario-authoring.md
  - notes/ownership-transfer.md
relevant_packages:
  - vultron/bt
  - vultron/core
---

# Event-Driven Control Flow Design Notes

## Overview

Vultron is designed as an event-driven system: actors react to events by
running behaviors, which may emit further events to other actors. This file
captures the conceptual model behind that design, the rationale for key
decisions, and guidance for understanding where the system should (and should
not) do work automatically.

**Formal requirements**: `specs/event-driven-control-flow.yaml` (EDF-01
through EDF-05)

**Related notes**: `notes/protocol-event-cascades.md` (concrete cascade gap
inventory and fix guidance), `notes/bt-integration.md` (BT design decisions),
`notes/bt-composability.md` (composable subtree patterns)

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
full **cascade chain** described in `specs/event-driven-control-flow.yaml`
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

## Temporal Sequence vs. Causal Sequence

(CONCERN-2181, ADR-0058. Normative requirements: `specs/event-driven-control-flow.yaml`
EDF-06; `specs/multi-actor-demo.yaml` DEMOMA-22.)

A scenario script is a list of steps, so it is natural to write it as a temporal
sequence: *A, and then B, and then C*. The protocol it drives is not temporal —
it is causal: *A, **therefore** B, **therefore** C*. Every place those two
readings differ is a race, because a trigger endpoint returns HTTP 202 and the
effect is committed later, by a `BackgroundTasks` job, on a different container.

The distinction is not stylistic. Seven of the nineteen sub-issues of Epic #2136
were the same defect in a different scenario: a step ran before the event that
would enable it had propagated. Bug #2178's triage put it exactly: *"the demo
treated async causal steps as sequential (x then y) rather than causally linked
(x therefore y)."*

### The chain each step sits in

A cross-actor step is never one event. It is a chain, and a gate can be placed
at any link — but only the last link proves the step's precondition:

```text
A addresses → A sends → delivered to B's inbox → B processes → B commits → B replies
                     ↑                        ↑                        ↑
              "sent" (sender-side)     "delivered"            "committed" ← gate here
```

Gating on an earlier link is the recurring error. `notes/demo-ci-diagnostics.md`
names the same three layers — Sent, Received, Committed — for reading a failed
run; the gate belongs at Committed.

### Three rules that follow

1. **Gate on the effect, observed where it lands.** The predicate must be a
   property of the actor that *commits* the effect, read from that actor's own
   container. A sender-side observation proves only that the sender emitted
   something (EDF-06-002).

2. **A synchronous observable is not evidence of an asynchronous effect.** In
   #2134, `engage-case` was gated on "the case object exists" — which resolves
   synchronously during `validate-report` — instead of "this participant reached
   `RM.VALID`", which commits after the 202 returns. The first is a proxy for the
   cause having *started* (EDF-06-003).

3. **Find a caused object by what it is, not by the ID of its cause.** When a
   received-side use case forwards a *new* activity, the consequent has a new
   identity. In #2178 the demo polled for the original Offer ID; the Coordinator
   only ever held the forwarded Offer, with a different ID (CM-21-005). Scan for
   semantic properties — type, target, object — as `find_case_invite_for_actor`
   and `find_cp_offer_for_case` do (EDF-06-004). The #2178 fix adds
   `find_ownership_transfer_offer_for_actor` in the same shape; it arrives with
   the `fix/demo-ci` integration branch.

### A gate must actually gate

Expressing a precondition with an advisory check is worse than having none: it
reads like a gate in review and does nothing at runtime. `demo_check` records a
failure and returns, so the dependent step runs anyway on state that was never
established, and the resulting cascade of secondary failures buries the real one.

Use `demo_gate` for a causal precondition and `demo_check` for a verification
assertion. `demo_gate` accumulates identically — DEMOCI-01-003's
report-everything contract is preserved — and additionally stops the steps that
depend on the unmet precondition (DEMOCI-01-007, EDF-06-005).

When writing tests for a gate, exercise the real context manager. Patching it out
with `contextlib.nullcontext` makes the assertion propagate and the test pass
while proving nothing about gating. This idiom is currently used in seven demo
test modules, so no test in the suite exercises the real control flow of these
context managers — which is how the advisory `RM.VALID` gate before `engage-case`
went unnoticed.

### Not every wait is a defect

Some waits are irreducibly temporal and must stay: service liveness probes,
protocol deadlines such as embargo expiry, and transport retry backoff. Name them
as temporal at the call site so they are not "fixed" into meaningless causal
gates, and so the causal-gate inventory stays honest (EDF-06-006).

Some preconditions are not observable at all today. An actor having *processed* a
delivery leaves no completion record — the inbox receipt log records arrival, and
processing happens in a background task. Every "processed" gate is therefore
inferential: it observes a downstream effect and assumes the antecedent caused it.
When a precondition cannot be expressed as an observable predicate, record that
gap rather than substituting a `sleep` (EDF-06-007).

### Where this stops being a harness problem

Harness-side gating cannot fix a cause that never becomes observable. #2169's
finder race is server-side fan-out, and a client-side wait cannot prevent it; the
real fix was actor-side buffering (ADR-0037, and ADR-0059 for pre-genesis
ledger-entry buffering). Where the actor buffers, the harness needs no gate at all — so some
existing `wait_for_case_on_container` sites may be removable.

The test for which side owns a race: if the effect is *eventually* guaranteed by
a wired recovery path, the harness may wait for it. If the effect can be *lost*,
the protocol must buffer it, and a demo guard is papering over a production bug.

### Scenario narratives as a conformance oracle

A gate enforces that the harness waited for the right thing. It cannot tell you
whether the ordering the scenario encodes is the ordering the CVD process
actually requires — the script is the only statement of intent, so it cannot
disagree with itself.

That is what the narratives under `docs/topics/scenarios/` are for: one page per
scenario describing the case's progress in domain terms, with each step's
antecedent named and no reference to endpoints, helpers, or containers. Because it
is written independently of the implementation, it can contradict it. Each
narrative carries a machine-readable list of causal edges, and the invariant
harness asserts every declared edge appears in the observed case ledger with the
antecedent's `log_index` before the consequent's — `log_index` order is causal
order (ADR-0079, CLP-14-001), and the harness already reads the ledger dumps
(DEMOMA-22-003 through DEMOMA-22-006).

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

In the prototype, an external decision node **requests the input it needs and
terminates**. It does not return `RUNNING` and it does not wait: EDF-04-002
forbids that (reversed by ADR-0080), and the framework could never have honoured
it — `BTBridge.execute_tree` treats root `RUNNING` as "keep ticking", exhausts
its iteration budget, logs `ERROR`, returns `FAILURE`, and then discards the tree
in `finally: bt.shutdown()`, so there is no instance left to resume. No node in
`vultron/` returns `Status.RUNNING`.

The required input arrives later as a trigger invocation or an inbox message,
and its arrival drives a **fresh** evaluation (EDF-04-003) whose first act is to
determine where the exchange stands (ASK-02-001). Where the input is another
actor's decision, this is the protocol-ask primitive: emit the ask, terminate
with `SUCCESS` meaning *I asked* (ASK-01-002), and let the reply start new work.
See [protocol-asks.md](protocol-asks.md) and ADR-0080.

A terminal status with **no request emitted** is the silent failure EDF-04-005
forbids — the emitted request is the observable that distinguishes "asked and
waiting" from "gave up".

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
| External stops | Explicit ask-and-terminate nodes | Absence of code is invisible; an emitted request documents the intent and is observable (EDF-04-002, ASK-01-002) |
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
# ✅ CORRECT — demo triggers primary event, verifies outcome
post_to_trigger(client, vendor_id, "validate-report", body=report_params)
# ... poll for settlement ...
wait_for_case_on_container(dl, case_id)        # observe state, not steps
assert_participant_added(dl, case_id, finder_id)
```

> **Note (CONCERN-1635):** The earlier form of this example used
> `post_to_inbox_and_wait(client, vendor_id, validate_activity)` and was marked
> ✅ CORRECT for "demo injects primary event." That pattern is now superseded.
> CONCERN-1635 prohibits demo scripts from POSTing directly to any actor's inbox
> — including via `post_to_inbox_and_wait` — even for the primary event. The
> correct pattern is `post_to_trigger` + a polling assertion
> (`wait_for_case_on_container`, `find_case_invite_for_actor`, etc.). See the
> CONCERN-1635 rule in `vultron/demo/AGENTS.md`.

### Missing External Decision Node

```python
# ❌ WRONG — BT does nothing, cascade never fires, no signal of why
class SuggestActorReceivedUseCase:
    def execute(self) -> None:
        _idempotent_create(self._request)
        # (silence — no BT, no explanation of why no cascade)
```

```python
# ✅ CORRECT — BT runs, routes on conversation state, asks and terminates
class SuggestActorReceivedUseCase:
    def execute(self) -> None:
        _idempotent_create(self._request)
        tree = create_recommend_actor_to_case_received_tree(...)
        bridge.execute_with_setup(tree, actor_id=case_owner_id)
        # The tree's Selector routes on where the exchange stands — already a
        # participant / invite in flight / owner asked and unanswered / fresh —
        # reading open/closed state from the ledger via find_protocol_pair.
        # The fresh branch emits Offer(CaseParticipant) to the owner and returns
        # SUCCESS, meaning "I asked". Nothing returns RUNNING and nothing waits;
        # the owner's Accept or Reject arrives as its own inbound message and
        # drives its own tree.
```

`create_recommend_actor_to_case_received_tree`
(`vultron/core/behaviors/case/suggest_actor_tree.py`, ADR-0026 / CM-16) is the
working reference implementation of this shape — see
[protocol-asks.md](protocol-asks.md), which describes generalising it.

---

## Demo Categories: Exchange vs. Scenario

(BUG-26041701, 2026-04-17)

There are two fundamentally different kinds of Vultron demos:

### Exchange Demos (`vultron/demo/exchange/`)

Demonstrate individual protocol message exchanges in isolation. These
**intentionally** use direct inbox injection ("spoofing") because they show
protocol fragments, not end-to-end behavior. The sending actor's BT and outbox
are bypassed by design.

- **Examples**: `receive_report_demo.py`, `suggest_actor_demo.py`
- **Pattern**: Construct AS2 activity manually → POST to recipient inbox
- **Purpose**: Unit-level demonstration of a single message exchange

### Scenario Demos (`vultron/demo/scenario/`)

Demonstrate full multi-actor workflows. These MUST use trigger endpoints
("puppeteering") so the system's own BT and outbox logic is exercised.

- **Examples**: `fv_demo.py`, `three_actor_demo.py`,
  `multi_vendor_demo.py`
- **Pattern**: Call trigger endpoint on sending actor's container → actor's
  BT runs → activity added to outbox → outbox handler delivers to recipient
- **Purpose**: Integration-level demonstration of complete protocol flows

### Why the Distinction Matters

Direct inbox injection ("spoofing") in scenario demos violates the principle
that all inter-actor communication flows through the AS2 outbox/inbox pipeline.
It also bypasses the BT, meaning the system's autonomous cascade behavior is
never exercised. Demos that spoof instead of puppeteer **hide implementation
gaps** — they look correct while the actual trigger + BT path is broken.

### Correct Participant Invitation Workflow

The recommended protocol sequence for adding a new participant (replacing
manual invitation spoofing):

```text
1. Coordinator → trigger suggest-actor-to-case
       ↓ creates RecommendActorActivity(actor=coordinator, object=invitee, target=case)
       ↓ added to coordinator outbox → delivered to case_actor inbox

2. Case-actor receives RecommendActorActivity
       ↓ BT: verify case_actor IS the case owner (attributed_to check)
       ↓ BT: emit AcceptActorRecommendationActivity(to=[coordinator])
       ↓ BT: emit RmInviteToCaseActivity(actor=case_actor, object=invitee, target=case, to=[invitee])
       ↓ both activities added to case_actor outbox → delivered

3. Invitee → trigger accept-case-invite
       ↓ creates RmAcceptInviteToCaseActivity(actor=invitee, object=invite, to=[case_actor])
       ↓ added to invitee outbox → delivered to case_actor inbox

4. Case-actor receives RmAcceptInviteToCaseActivity
       ↓ existing AcceptInviteActorToCaseReceivedUseCase handles this correctly
```

The case_actor acts **autonomously** — it doesn't need to be told "now send
an invite." This is modeled as a BT triggered by the receive use case.

### Outbox Expansion Bridge for Transitive Activities

`_dehydrate_data` in `db_record.py` intentionally collapses `object_` dict
values to ID strings during storage to avoid redundant inline storage. The
outbox expansion bridge is the correct compensating mechanism: for each
activity type delivered via outbox, expand bare-string `object_` back to its
full typed form before wire delivery.

The bridge MUST be extended for all transitive activity types that go through
the dehydrate/rehydrate cycle. The current set requiring expansion: `"Create"`,
`"Announce"`, `"Add"`, `"Invite"`, `"Accept"`. Additional types (`"Join"`,
`"Remove"`) may need the same treatment as they are implemented.

If `dl.read(activity_object)` returns `None` at delivery time, log a warning
and skip delivery (matching current `Create`/`Announce` behavior).
