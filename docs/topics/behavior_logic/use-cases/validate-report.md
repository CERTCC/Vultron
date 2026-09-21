# Validate Report

Validating a report is the decision that a received report describes a real problem worth coordinating.
It is the first place in the protocol where a Participant applies its own judgment to something another actor sent it, and the first place where that judgment becomes visible to everyone else in the case.

This page explains what the step decides, which parts of it are settled mechanically, and which part the protocol cannot settle for you.

---

## What starts it

Two paths reach this behavior, and they differ only in whose state moves.

A Participant runs it **for itself** when it decides a report it holds is valid.
The reference implementation exposes this as the `validate_report` trigger.

A Participant runs it **about another actor** when an inbound `Accept(Offer(VulnerabilityReport))` arrives — the wire form of the Report Valid (RV) message — telling it that the sender has validated the report.
The receiving actor then records the *sender's* Report Management (RM) transition, not its own.
The behavior runs in the receiving actor's own store, and the actor whose state advances is named by the message rather than inferred from which store is executing (CLP-10-015).

Either way the step is guarded by RM state.
An actor at `RM.RECEIVED` or `RM.INVALID` may proceed; anything else may not.
A report already at `RM.VALID` takes an early exit and succeeds without doing anything, so a repeated trigger or a redelivered message is harmless.

!!! note "Validation follows intake, but is not part of it"

    A Participant enters `RM.RECEIVED` when a report arrives, and creating the case
    and its participants happens there
    ([ADR-0041](../../../adr/0041-caseactor-authoritative-case-initialization.md)).
    Validation is a separate step that only moves state and announces the result.
    It never creates a case.

---

## The mechanical path

Five things are decided from recorded state alone.

| Check | What it establishes |
|---|---|
| Already valid? | The step is a no-op and returns success (ID-04-004) |
| RM is `RECEIVED` or `INVALID` | The transition to `VALID` is legal from here |
| A case for this report exists in *this* actor's store | The actor has the case replica the remaining work reads |
| An embargo end time is established | `RM.VALID` requires one (DUR-07-004) |
| The RM transition is permitted | A write validates `(current → target)` before persisting (RMB-15-001) |

Every one of those precedes the first write.
That ordering is load-bearing rather than tidy.
`RM.VALID` is case-scoped, and the case reaches a Participant only as a replica the case manager sends it ([ADR-0073](../../../adr/0073-per-actor-storage-isolation.md), PCR-01-003).
An actor that validates before its replica has arrived therefore does *nothing*, not half of the transition (RMB-15-001, DUR-07-004).
Suppose it writes the state latch and then fails the embargo check.
The latch now makes every later attempt take the early exit, and the two halves can never reconverge.

---

## Where judgment enters

Two call-out points sit between the preconditions and the effects, and they ask different questions.
Both are Evaluators in the [ADR-0024](../../../adr/0024-coordination-agent-taxonomy.md) capability-shape taxonomy, and both are injected as swappable backends rather than hard-coded ([ADR-0025](../../../adr/0025-call-out-point-abstraction-layer.md)).

**EvaluateReportCredibility** (Evaluator) asks whether the source and the claim are believable enough to spend effort on.
This is a judgment about the *report*, not the vulnerability.
A terse note from a Reporter with a track record and an anonymous submission carrying a working proof of concept are both credible.
A vague claim with no reproduction steps, from an unknown sender, may not be.

**EvaluateReportValidity** (Evaluator) asks whether the reported condition is a real vulnerability in a product this actor is answerable for.
A report can be entirely credible and still invalid — intended behavior, a misconfiguration, or a product this actor does not maintain.
A duplicate is *not* an example: it describes a real vulnerability, so it is valid, and marking it invalid is specifically ruled out (RMB-11-002, discussed below).

The order matters.
Credibility gates effort, validity gates ownership, and an actor that evaluates validity first ends up investigating claims it had no reason to take seriously.
Both are Evaluators because the answer is a recommendation grounded in policy and expertise rather than a fact anyone can look up.
Their service contracts are in the [Capability Model](../../capability_model/index.md#report-validation).

Either Evaluator can stop the step by returning failure (BT-18-007).
Under the deterministic default backend both accept, so a deployment that has wired nothing will validate every report it receives (BT-23-001).
That is a property of the stub and not a protocol position.

A third call-out point, **GatherValidationInfo** (Retriever), belongs to this use case but is not yet wired into the reference implementation.
It exists for the case the original design treats as ordinary: a report held at `RM.INVALID` because information was missing, revisited when that information arrives (RMB-11-003).
The reference implementation has no invalidation arm and no information-gathering loop, so today the step either validates or fails.

---

## What the case learns

On success the actor emits a `validate_report` activity — `Accept(Offer(VulnerabilityReport))` on the wire, RV in the formal message set — addressed to the actor holding `CVDRole.CASE_MANAGER`.

Addressing it there is not a routing detail.
The case manager's inbox is what authors the canonical ledger entry for the event, so an activity that does not reach the case manager leaves no record in the case's shared history (CLP-10-001, [ADR-0021](../../../adr/0021-caseactor-inbox-routing-canonical-ledger.md)).
The case manager then replicates that entry to the other Participants, which is how they learn this actor's RM state changed.
The emitting actor does not fan the message out itself (PCR-08-001).

Emission failure does not fail the step.
The outbox owns delivery retry ([ADR-0066](../../../adr/0066-outbox-terminal-state.md)), and the received-side path emits nothing at all, because the message it is handling *is* that announcement and re-emitting it would loop.

---

## What conformance requires

A conformant Participant need not use behavior trees, or make the same judgment calls.
It must satisfy the RMB requirements for this step.

| Requirement | Obligation |
|---|---|
| [RMB-09-001](../../../reference/specs/protocol.md#rmb-09) | A Participant entering `RM.RECEIVED` SHOULD start a validation process |
| [RMB-10-001](../../../reference/specs/protocol.md#rmb-10) | A Participant entering `RM.VALID` MUST start a prioritization evaluation |
| [RMB-10-002](../../../reference/specs/protocol.md#rmb-10) | A Participant MUST NOT close a report directly from `RM.VALID` |
| [RMB-10-003](../../../reference/specs/protocol.md#rmb-10) | A Participant entering `RM.VALID` SHOULD emit RV |
| [RMB-11-001](../../../reference/specs/protocol.md#rmb-11) | A Participant entering `RM.INVALID` SHOULD emit Report Invalid (RI) |
| [RMB-11-002](../../../reference/specs/protocol.md#rmb-11) | Duplicate reports SHOULD NOT be marked invalid |
| [RMB-15-001](../../../reference/specs/protocol.md#rmb-15) | An RM write MUST validate the transition before persisting |

Two of those are easy to miss.
RMB-10-001 means validation is never the end of the path: reaching `RM.VALID` obliges the actor to decide whether to engage or defer, which is the [Prioritize report](prioritize-report.md) use case.
RMB-11-002 rules out the most tempting use of `RM.INVALID`.
A duplicate is a real vulnerability that this actor already knows about.
Marking it invalid tells other Participants something false about the vulnerability rather than something true about the report.

---

## Further reading

- [Report Validation Behavior](../rm_validation_bt.md) — the original design tree, including the invalidation and information-gathering arms
- [Prioritize report](prioritize-report.md) — the step RMB-10-001 requires next
- [Report Management Handlers](../../../reference/behaviors/rm_handlers.md) — the tree the reference implementation builds today
- [The Received (R) state](../../process_models/rm/index.md#the-received-r-state) — where the credibility-then-validity ordering comes from
- [Glossary](../../../reference/glossary.md) — Participant, call-out point, capability shape, report validity
