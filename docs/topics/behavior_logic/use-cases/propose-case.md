# Propose Case

Proposing a case is how an actor asks a service to open and manage a coordination case on its behalf.
The proposing actor does not create the case itself.
It sends a proposal and waits, and the service that accepts becomes the single-writer authority for everything that follows.

This page explains why the protocol delegates case creation rather than performing it locally, what the accepting service does on the proposer's behalf, and where the decision to accept or decline lives.

---

## What starts it

An actor that holds a report and wants it coordinated as a case sends `Create(as_CaseProposal)` to a **case actor service** — the provisioning endpoint configured as `case_actor_service_url` (CP-04-001, CP-08-002).
In the reference implementation this happens inside the `create_case` trigger path: the actor records a local case, publishes the case actor identity it will address, and emits the proposal.

The proposal carries the report inline.
A URI reference is not permitted, because the receiving service has no way to read anything out of the proposer's store (CP-01-004, AKM-03-001).
It also carries the provenance of the report — which `Offer(VulnerabilityReport)` delivered it and from whom — because the accepting service cannot reconstruct that and needs it for the first ledger entry (CP-01-007).

The proposal is addressed to the service's container identity, never to an identity derived per case or per report (CP-04-003).
The service does not exist yet as a per-case actor; that is what is being asked for.

!!! note "Why not just create the case locally?"

    An actor can hold a local case object. What it cannot do alone is be the
    **single-writer authority** for a case that other organizations will replicate
    from. The `CVDRole.CASE_MANAGER` role carries that authority, and the
    canonical ledger every participant converges on is written by whoever holds
    it ([ADR-0041](../../../adr/0041-caseactor-authoritative-case-initialization.md)).
    Delegating creation is how the authority gets established as a fact other
    actors can recognise, rather than a claim the proposer makes about itself.

---

## The mechanical path

Accepting a proposal is the largest single cascade in the protocol.
The accepting service does eleven things, and the order is not interchangeable.

| Step | What it establishes |
|---|---|
| Resolve or create the case | A duplicate proposal reuses the existing case rather than creating a second (CP-05-006) |
| Store the inline report | Everything downstream derives from it — the reporter participant, its ledger entry, the consent seed |
| Add itself as participant | COORDINATOR and CASE_MANAGER, so the authority is in the roster |
| Add the proposing actor | CASE_OWNER at `RM.RECEIVED`, plus whatever roles its configuration declares |
| Add the reporter | At `RM.ACCEPTED` — the reporter has already accepted, by reporting |
| Initialize the default embargo | A case begins embargoed rather than open (EP-04-001) |
| Seed the owner's consent | SIGNATORY, without an invitation round-trip |
| Seed the reporter's consent | SIGNATORY — submitting a report is implicit consent ([ADR-0048](../../../adr/0048-pec-no-embargo-is-absence-not-pre-consent.md)) |
| Commit the canonical ledger entries | The case's history starts here |
| Emit `Accept(as_CaseProposal)` | The proposer learns its request succeeded |
| Emit `Create(VulnerabilityCase)` | The proposer receives the case replica, with participants inline |

The two emissions are separate steps for a reason worth understanding.
The `Accept` is irrevocable once sent: the service has committed to managing the case.
The replica delivery can still fail.
So a durable marker is written between them, and a retry runner completes only the `Create` — never resending the `Accept` (CP-05-005).
Sending a second `Accept` would tell the proposer it had been accepted twice, and there is no such thing.

---

## Where judgment enters

One call-out point governs this use case: **EvaluateCaseProposal** (Evaluator), the admission decision (CP-05-002).

It is the only place a deployment can express admission policy.
Whether the proposing actor is one this service will work for, whether it already holds more open cases than the service will carry, whether the inline report is substantive enough to be worth coordinating — all of that lives here or nowhere.

The decision is placed ahead of every one of the eleven steps above, and that placement is the interesting part.
A refusal has to happen before the case exists.
A service that created the case, committed ledger entries, and *then* declined would be telling the proposer "no" while holding a half-built case that no participant will ever converge on — the canonical-versus-replica divergence CLP-10-009 exists to prevent.

When the service declines, it sends `Reject(as_CaseProposal)` with the proposal inline, and creates nothing (CP-05-004).
The proposing actor records the refusal (CP-06-003, CP-06-004).

The refusal is recorded before it is sent, and that ordering carries weight.
A decline that cannot be delivered must not silently become an acceptance, so the service writes the decision down first and refuses to run the accept path afterwards.
The consequence a reader should expect: a service that decided "no" and then failed to say so reports a processing failure, and retries the refusal on the next delivery — it never creates the case.

The reason for a refusal is a separate matter.
CP-06-004 requires the proposer to surface one where present, but nothing yet carries a reason from the admission decision onto the wire: a call-out point signals refusal by returning failure, and the blackboard contract in BT-18 defines outputs only for the success case.
Until that channel is designed the `Reject` carries no `summary`, so a proposer records the refusal without an explanation ([#3399](https://github.com/CERTCC/Vultron/issues/3399)).

Under the deterministic default the service admits.
That default is deliberate: a service an actor was configured to trust should not silently refuse, and refusing by default would mean no unconfigured deployment could ever open a case.
It is also not the conservative-default case that BT-23-012 governs, because accepting creates a *new* case in which the proposer becomes the owner — no other party's agreed state is touched.

An already-accepted proposal is never re-adjudicated.
A duplicate delivery reuses the existing case rather than deciding again, because a later "decline" would contradict an `Accept` already sent.
CP-05-006 goes further and requires the stored `Accept` to be re-sent unchanged, with its original identifier, so a proposer whose copy was lost converges rather than waiting forever; the reference implementation reuses the case but does not yet re-send ([#2890](https://github.com/CERTCC/Vultron/issues/2890)).

---

## What the case learns

The proposer receives two messages, in order: `Accept(as_CaseProposal)`, then `Create(VulnerabilityCase)` carrying the case with its participants inline.
The `Create` sets `context` to the new case's URI and `in_reply_to` to the `Accept` that authorized it, so the causal link is explicit in the AS2-correct field (CP-05-003, [ADR-0045](../../../adr/0045-create-vulnerability-case-field-assignment.md)).

On a declined proposal the proposer receives `Reject(as_CaseProposal)` and nothing else.

No other actor learns anything yet.
At this point the case has three participants — the authority, the owner, and the reporter — and no one has been invited.
Bringing in a vendor or a coordinator is a separate flow.

!!! warning "A proposal with no answer is not a proposal still pending"

    A proposer that has received neither an `Accept` nor a `Reject` by the
    proposal's deadline MUST treat it as expired and stop waiting (CP-05-007).
    Nothing in the protocol will eventually resolve it, because nothing is
    holding it open — see
    [Protocol Event Flow](../../protocol_flow.md#deadlines-need-something-to-notice-them)
    for why a deadline passing is not an event.

---

## What conformance requires

| Requirement | Obligation |
|---|---|
| [CP-04-001](../../../reference/specs/protocol.md#cp-04) | A proposer MUST send `Create(as_CaseProposal)` to the case actor service's inbox |
| [CP-04-003](../../../reference/specs/protocol.md#cp-04) | The proposal MUST be addressed to the service's container identity, not a per-case one |
| [CP-05-002](../../../reference/specs/protocol.md#cp-05) | The service MUST evaluate the proposal and either accept or reject it |
| [CP-05-003](../../../reference/specs/protocol.md#cp-05) | On acceptance it MUST send `Accept` and then `Create(VulnerabilityCase)`, in that order |
| [CP-05-004](../../../reference/specs/protocol.md#cp-05) | On refusal it MUST send `Reject(as_CaseProposal)` with the proposal inline |
| [CP-05-005](../../../reference/specs/protocol.md#cp-05) | A failed `Create` MUST be retried without resending the `Accept` |
| [CP-05-006](../../../reference/specs/protocol.md#cp-05) | A duplicate proposal MUST re-send the stored `Accept` unchanged, with its original identifier, and MUST NOT create a second case |
| [CP-05-007](../../../reference/specs/protocol.md#cp-05) | A proposer MUST treat an unanswered proposal as expired at its deadline |
| [CP-06-003](../../../reference/specs/protocol.md#cp-06) | The proposer MUST record the acceptance and await the replica |
| [CP-06-004](../../../reference/specs/protocol.md#cp-06) | The proposer MUST record a refusal and surface its reason where one is given |

The requirement most often read too loosely is CP-05-002.
"Evaluate and either accept or reject" is not satisfied by a service that always accepts.
An implementation with no refusal path has no admission policy, and a case actor service that cannot decline is an open relay: any actor able to reach the inbox obtains a managed case, a canonical ledger, and a default embargo.

---

## Further reading

- [Case Initialization](../../case_lifecycle/case_initialization.md) — the wider bootstrap sequence this use case starts
- [Validate report](validate-report.md) — what the owner does once the case replica arrives
- [Embargo lifecycle](embargo-lifecycle.md) — the default embargo this use case creates, and how it is renegotiated
- [Case Handlers](../../../reference/behaviors/case_handlers.md) — the tree the reference implementation builds today
