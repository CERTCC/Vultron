---
stakeholder_type: [platform-developer]
level: 300
contents: generated
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

Each entry names the trigger endpoint that starts the use case.

<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml nav or a listed page's description: frontmatter, then run `uv run docs-site --write` -->

- [Validate Report](validate-report.md) — Trigger `validate_report`: deciding that a received report is worth coordinating, and advancing RM to `VALID`.
- [Prioritize Report](prioritize-report.md) — Triggers `engage_case` and `defer_case`: choosing whether to work the case now or park it, and announcing which.
- [Propose Case](propose-case.md) — Trigger `create_case`: asking a case actor service to open and manage a case, and what it does on acceptance.
- [Embargo Lifecycle](embargo-lifecycle.md) — Triggers `propose_embargo`, `accept_embargo`, `reject_embargo`, and `terminate_embargo`: negotiating, joining, revising, and ending an embargo.

<!-- END GENERATED SECTION CONTENTS -->

---

## Further reading

- [Protocol Event Flow](../../protocol_flow.md) — the actor model, cascades, and what happens when an actor must ask permission
- [Capability Model](../../capability_model/index.md) — the four capability shapes and the full catalog of call-out points
- [Behaviors Reference](../../../reference/behaviors/index.md) — the trees the reference implementation builds today
- [Behavior Logic](../index.md) — the original behavior tree design these use cases realize
- [Glossary](../../../reference/glossary.md) — Participant, call-out point, capability shape, case actor service
