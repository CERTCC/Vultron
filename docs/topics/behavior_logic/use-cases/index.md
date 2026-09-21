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

The useful distinction in a use case is not between "simple" and "complex" steps.
It is between decisions the protocol can settle from what it already knows and decisions it cannot.

A **mechanical** decision reads recorded state and applies a rule.
Is this Participant already in the Valid (RV) state of the Report Management (RM) machine, does this case exist in this actor's own store, is this transition permitted by the state machine.
Two conformant implementations will reach the same answer, because the rule and the inputs are both fixed.

A **delegated** decision has no answer in the record.
Whether a report is credible, whether embargo terms are acceptable, whether a vulnerability merits a Common Vulnerabilities and Exposures (CVE) identifier — these depend on policy, expertise, or facts held outside the protocol.
The protocol marks the location and defines what an answer looks like; it does not supply the answer.
Two conformant implementations may legitimately differ here, and that is the point of the seam.

This is why a use-case page is worth reading separately from the tree that implements it.
The tree shows the nodes in order.
The page tells you which of those nodes your organization owns.

---

## How call-out points behave

A call-out point is a location where an actor obtains a judgment, a fact, or an artifact from outside the protocol ([ADR-0024](../../../adr/0024-coordination-agent-taxonomy.md)).
Five shapes cover every one of them: **Evaluator** returns a recommendation, **Retriever** returns facts, **Composer** returns content, **Actuator** confirms a side effect, and **Sentinel** watches a condition and calls a trigger endpoint instead of being called.
The shapes and their service contracts are described in the [Capability Model](../../capability_model/index.md).

Three properties of a call-out point matter when reading these pages.

It answers synchronously.
A call-out point returns success or failure and never leaves the tree running (BT-18-011).
An Evaluator that wants to block the step returns failure rather than reporting a rejection in its output (BT-18-007).

It has a default.
Every call-out point is injected through a backend factory with a deterministic default, so a deployment that supplies nothing still runs (BT-18-004, BT-23-001, [ADR-0025](../../../adr/0025-call-out-point-abstraction-layer.md)).
The default is usually the permissive one, on the reasoning that a stub should not silently withhold progress.
One class of gate inverts that.
Where a permissive default would let a party other than the case owner force a case-state change or an embargo teardown, the default is the conservative answer instead (BT-23-012, [ADR-0076](../../../adr/0076-security-significant-gates-default-require-case-owner-approval.md)).
When a page says a call-out point "defaults to accept", that is the stub's behavior and not a protocol requirement to accept.

It is not the same as asking another actor.
A call-out point asks a service the deploying organization runs, so it can be answered while the step is still in progress.
A question that needs a decision from another Participant — whether the case owner permits a change to the case's agreed state — cannot work that way.
There the actor sends a request and finishes, and the reply starts fresh work when it arrives ([ADR-0080](../../../adr/0080-protocol-asks-not-suspended-behaviors.md)).
Both appear in these pages, and confusing them leads to an implementation that waits for something that is never going to arrive.

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
- [Capability Model](../../capability_model/index.md) — the five capability shapes and the full catalog of call-out points
- [Behaviors Reference](../../../reference/behaviors/index.md) — the trees the reference implementation builds today
- [Behavior Logic](../index.md) — the original behavior tree design these use cases realize
- [Glossary](../../../reference/glossary.md) — Participant, call-out point, capability shape, case actor service
