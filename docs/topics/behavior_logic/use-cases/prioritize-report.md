---
stakeholder_type: [platform-developer]
level: 400
---

# Prioritize Report

Prioritizing a report is the decision to work a case now or to park it.
The protocol requires the decision but takes no position on the answer, because the answer depends on the Participant's workload, its obligations, and its own assessment of the vulnerability.

This page explains why the step is mandatory, what the two outcomes commit the actor to, and why the protocol treats parking a case as an announcement rather than as silence.

---

## What starts it

Reaching `RM.VALID` — the Valid state of the Report Management (RM) machine — obliges a Participant to prioritize (RMB-10-001).
There is no path from `RM.VALID` to closure, so an actor that validates a report and then does nothing has stalled rather than finished (RMB-10-002).

The decision resolves into one of two protocol steps, exposed by the reference implementation as the `engage_case` and `defer_case` triggers.
Engaging moves the Participant to `RM.ACCEPTED`; deferring moves it to `RM.DEFERRED`.
Neither is terminal: a deferred case can be engaged later when circumstances change, which is the whole reason `RM.DEFERRED` exists as a state rather than as a synonym for closed.

A Participant also runs this behavior **about another actor**, when an inbound `Join(VulnerabilityCase)` — the Report/Case Accepted (RA) message — or `Ignore(VulnerabilityCase)` — Report/Case Deferred (RD) — tells it that a peer engaged or deferred.
There the actor updates its record of the sender's RM state; its own state does not move (RMB-05-001, RMB-04-001).

---

## The mechanical path

On the deciding side, the mechanics are thin.
The actor transitions its own RM state and sends the corresponding message to the case manager.
There is nothing to compute, because the decision has already been made by the time this path runs.

On the receiving side the mechanics carry more weight, and their ordering is fixed.

| Step | Why it is where it is |
|---|---|
| The sending actor has a participant record in this case | An RM state with no participant to hold it is not a state the case can record |
| Commit the canonical ledger entry | The arrival is recorded before anything acts on it (CLP-10-006) |
| Transition that participant's RM state | Idempotent — a repeated message finds the state already set and succeeds |
| Resolve who may receive the case update | Embargo consent decides who is eligible |
| Broadcast the updated case | Participants learn the new roster state |

The commit sits between the guards and the effects, and never after them.
A tree that applies an effect and then refuses the message has written a canonical entry describing something the replica does not reflect, and canonical and replica state diverge permanently (CLP-10-009, CLP-10-011).
The practical rule for implementers: anything that can *refuse* an inbound assertion belongs before the commit, and anything that *acts* on it belongs after.

---

## Where judgment enters

**EvaluateCasePriority** (Evaluator) is the decision itself: given this case, should this actor engage it or defer it?
Evaluator is one of the four capability shapes ([ADR-0097](../../../adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md), BT-18-013); the backend answering it is injected, not compiled in ([ADR-0025](../../../adr/0025-call-out-point-abstraction-layer.md)).

This is the natural home for a Stakeholder-Specific Vulnerability Categorization (SSVC) integration, or for any prioritization scheme an organization already runs.
The protocol asks for a decision, not for a methodology, and deliberately says nothing about which inputs a Participant should weigh.
Under the deterministic default the answer is always engage, so an unconfigured deployment takes the happy path rather than quietly deferring everything.

**OnAccept** and **OnDefer** (Actuators) fire after the respective transition.
They are hooks, not decisions: an Actuator confirms that a side effect happened in an outside system — a ticket opened, a queue updated, an on-call rotation notified — and produces no content the protocol reads.
The distinction matters when choosing what to build.
If your service records a decision the tree then acts on, it is an Evaluator.
If it carries out an effect elsewhere and reports back, it is an Actuator.

Two further call-out points belong to this use case and are not yet wired: **EnoughPrioritizationInfo** (Evaluator) and **GatherPrioritizationInfo** (Retriever).
They serve the loop the original design treats as normal — a decision that cannot be made yet, deferred pending information, and revisited when it arrives (RMB-12-002).
The reference implementation decides once.

---

## What the case learns

Engaging emits `Join(VulnerabilityCase)`, the wire form of RA.
Deferring emits `Ignore(VulnerabilityCase)`, the wire form of RD.
Both are addressed to the actor holding `CVDRole.CASE_MANAGER`, which commits the canonical ledger entry and replicates it onward (PCR-08-001, CLP-10-001).

Deferral is announced, and this is the design decision worth pausing on.
Telling the other Participants that you have parked a case is unhelpful to you and useful to them.
A coordinator learns not to wait on your fix, and another vendor learns that the timeline it assumed no longer holds.
Announcing it is "Avoid Surprise" applied to the least comfortable state to be in, and it is the reason RD exists as a message rather than as a private flag.

Deferral also does not mean leaving.
An actor in `RM.DEFERRED` is still a Participant, still bound by the embargo it consented to, and still receiving case updates.
Departing a case is a different step with a different message.

---

## What conformance requires

| Requirement | Obligation |
|---|---|
| [RMB-10-001](../../../reference/specs/protocol.md#rmb-10) | A Participant entering `RM.VALID` MUST start a prioritization evaluation |
| [RMB-12-001](../../../reference/specs/protocol.md#rmb-12) | A Participant entering `RM.DEFERRED` SHOULD emit RD |
| [RMB-12-002](../../../reference/specs/protocol.md#rmb-12) | A Participant in `RM.DEFERRED` SHOULD watch for information justifying reprioritization |
| [RMB-12-003](../../../reference/specs/protocol.md#rmb-12) | A Participant in `RM.DEFERRED` MAY close the report after a policy period of inactivity |
| [RMB-13-001](../../../reference/specs/protocol.md#rmb-13) | A Participant MUST be in `RM.ACCEPTED` before sending Report Status (RS) to another Participant |
| [RMB-13-002](../../../reference/specs/protocol.md#rmb-13) | A Participant entering `RM.ACCEPTED` SHOULD emit RA |
| [RMB-13-003](../../../reference/specs/protocol.md#rmb-13) | A Participant in `RM.ACCEPTED` SHOULD perform active work on the report |
| [RMB-15-001](../../../reference/specs/protocol.md#rmb-15) | An RM write MUST validate the transition before persisting |

RMB-13-001 is the constraint with the longest reach.
Only a Participant in `RM.ACCEPTED` may submit the report onward to another party, so engaging is the gate on the entire multi-party expansion of a case.
A Participant that defers has not merely postponed its own work — it has declined, for now, to bring anyone else in.

---

## Further reading

- [Report Prioritization Behavior](../rm_prioritization_bt.md) — the original design tree, including the information-gathering loop
- [Validate report](validate-report.md) — the step that obliges this one
- [Report Management Handlers](../../../reference/behaviors/rm_handlers.md) — the tree the reference implementation builds today
- [Capability Model](../../capability_model/index.md#report-prioritization) — service contracts for the prioritization call-out points
- [Glossary](../../../reference/glossary.md) — Participant, call-out point, capability shape, case engagement
