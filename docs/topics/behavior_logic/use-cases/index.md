---
stakeholder_type: [platform-developer]
level: 300
---

# Use-Case Behavior

Each page in this section takes one coordination use case and explains the structure of the behavior behind it.
The subject is the shape of the decision, not the code that carries it out.
Four things define that shape: what starts the behavior, which parts the protocol settles by itself, which parts it hands to an outside judgment, and what the rest of the case learns.

These pages are for implementers deciding what their own participant has to do at a given step, and for integrators deciding which judgments they will need to supply.
They assume the actor model and cascade behavior described in [Protocol Event Flow](../../protocol_flow.md).

---

## What a use case is here

A use case is one coordination step that a Participant can carry out — validate a report, engage or defer a case, open a case with a case actor service, respond to an embargo overture.
Each has a name the reference implementation exposes as a trigger endpoint, such as `validate_report` or `propose_embargo`.

A use case is not a message type and not a state transition.
It is the unit of work that sits between them: something happens, the actor works out what that means for its own state, and the protocol messages that follow are consequences rather than instructions.

---

## The anatomy every page follows

Each page answers the same five questions in the same order.

| Section | What it establishes |
|---|---|
| What starts it | The trigger or inbound message that puts the actor on this path, and the state the actor must already be in |
| The mechanical path | The checks and state changes the protocol settles without asking anyone |
| Where judgment enters | The call-out points — the places an actor must get an answer from outside the protocol — and the decision each one represents |
| What the case learns | The messages emitted, and who receives them |
| What conformance requires | The normative requirements a participant must satisfy, independent of behavior trees |

The order is deliberate.
Preconditions come before actions because a step that runs ahead of its preconditions does nothing at all rather than half the work.
Judgment comes before effects because a refusal has to be able to stop the step before anything is written or sent.

---

## Mechanical and delegated decisions

Each page separates the decisions the protocol settles from recorded state from the ones it hands to a system the deploying organization runs, the call-out points.
The tree shows the nodes in order; the page tells you which of those nodes your organization owns.
The [Capability Model](../../capability_model/index.md) explains the distinction, the [four shapes](../../capability_model/index.md#the-four-shapes) a call-out point takes, and how call-out points behave: they answer synchronously, they have a default when nothing is plugged in, and they are not the same as asking another actor ([Settled and open design questions](../../capability_model/index.md#settled)).
When a page says a call-out point "defaults to accept", that describes the default stub, not a protocol requirement to accept.

---

## The use cases

| Use case | Trigger name | What the page covers |
|---|---|---|
| [Validate report](validate-report.md) | `validate_report` | Deciding that a received report is worth coordinating, and advancing RM to `VALID` |
| [Prioritize report](prioritize-report.md) | `engage_case`, `defer_case` | Choosing whether to work the case now or park it, and announcing which |
| [Propose case](propose-case.md) | `create_case` | Asking a case actor service to open and manage a case, and what it does on acceptance |
| [Embargo lifecycle](embargo-lifecycle.md) | `propose_embargo`, `accept_embargo`, `reject_embargo`, `terminate_embargo` | Negotiating, joining, revising, and ending an embargo |

---

## Further reading

- [Protocol Event Flow](../../protocol_flow.md) — the actor model, cascades, and what happens when an actor must ask permission
- [Capability Model](../../capability_model/index.md) — the four capability shapes and the full catalog of call-out points
- [Behaviors Reference](../../../reference/behaviors/index.md) — the trees the reference implementation builds today
- [Behavior Logic](../index.md) — the original behavior tree design these use cases realize
- [Glossary](../../../reference/glossary.md) — Participant, call-out point, capability shape, case actor service
