---
title: CaseProposal Protocol
status: active
description: >
  Design rationale, protocol flow, and implementation guidance for the
  CaseProposal mechanism: a new AS2 object and message flow that separates
  "requesting case initialization" from "creating the case."
related_specs:
  - specs/case-proposal.yaml
  - specs/case-management.yaml
  - specs/embargo-policy.yaml
  - specs/semantic-extraction.yaml
  - specs/case-ledger-processing.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/case-communication-model.md
  - notes/bt-integration.md
  - notes/embargo-default-semantics.md
  - notes/bt-pitfalls.md
  - notes/call-out-configuration.md
  - notes/demo-scenario-authoring.md
  - notes/case-ledger-authority.md
  - notes/datalayer-design.md
relevant_packages:
  - vultron/wire/as2/vocab/objects
  - vultron/core/models/events
  - vultron/core/use_cases/received
  - vultron/core/behaviors/case
---

# CaseProposal Protocol

**Source**: 2026-06-22 grill-me planning session, issue #1081.
Normative requirements: `specs/case-proposal.yaml` (CP-01 through CP-09).
ADR: `docs/adr/0023-case-proposal-protocol.md`.
Refined by: `docs/adr/0041-caseactor-authoritative-case-initialization.md`
(supersedes ADR-0015; the CASE_MANAGER creates the case natively on proposal accept).

---

## Motivation

`CreateCaseActorNode` currently creates the CaseActor locally in the receiver's
DataLayer. When the case-actor service is external (issue #810), the receiver
needs a way to tell the case-actor service about a new case.

Sending `Create(VulnerabilityCase)` from the report receiver is not correct. In
ActivityStreams, `Create(X)` means "I created X." The report receiver is not the
authoritative creator of the case — the case-actor service is. Using the
receiver as `actor` on a `Create(VulnerabilityCase)` violates this semantics.

The `CaseProposal` object provides a clean solution: the receiver proposes that
the case-actor service create the case, while the case-actor service does the
actual creation.

---

## Protocol Flow

**Note**: The flow below reflects the corrected CASE_MANAGER-authoritative model
(ADR-0041). The report receiver does NOT create a `VulnerabilityCase` locally before
the CASE_MANAGER responds. The report receiver stores the report, writes a pending
`VultronReportCaseLink`, and waits.

```text
Report receiver                     CaseActor Service
  |                                       |
  | --- Create(CaseProposal) -----------> |
  |         actor: receiver URI           |
  |         object_: as_CaseProposal      |
  |                                       |
  |   [creates case, adds participants,   |
  |    initializes embargo, commits       |
  |    canonical ledger entries natively] |
  |                                       |
  | <-- Accept(CaseProposal) ----------- |  (happy path)
  |         actor: case-actor URI         |
  |         object_: as_CaseProposal      |
  |         result: case URI              |
  |                                       |
  | <-- Create(VulnerabilityCase) ------- |
  |         actor: case-actor URI         |
  |         context: case URI             |
  |         in_reply_to: Accept URI       |
  |         [inline participants]         |
  |                                       |
  |    -- OR --                           |
  |                                       |
  | <-- Reject(CaseProposal) ----------- |  (rejection path)
  |         actor: case-actor URI         |
  |         object_: as_CaseProposal      |
```

### Step 1: Report receiver sends `Create(as_CaseProposal)`

The report receiver creates an `as_CaseProposal` object containing:

- `id_`: auto-generated URI for the proposal
- `attributed_to`: the report receiver's actor URI (the future CASE_OWNER)
- `object_`: inline or URI-referenced `as_VulnerabilityReport`
- `target`: the case-actor service URI
- `summary` (optional): human-readable description

The report receiver then sends `Create(as_CaseProposal)` to the case-actor service's
inbox, with `actor=owner_uri`.

### Step 2a: Case-actor accepts (happy path)

When the case-actor service decides to create the case, it sends **two**
activities back to the report receiver:

1. **`Accept(as_CaseProposal)`** — acknowledgment that the proposal was
   accepted. `object_` embeds the `as_CaseProposal` inline.

2. **`Create(VulnerabilityCase)`** — the actual case creation announcement.
   - `actor` = case-actor URI (preserving AS2 "I created this" semantics)
   - `context` = URI of the new `VulnerabilityCase` (consistent with all
     other case-scoped activities; required for inbox deferral routing)
   - `in_reply_to` = URI of the `Accept(CaseProposal)` activity (causal
     antecedent, in the AS2-correct field for responses)

`in_reply_to` carries the Accept URI rather than putting it in `context`.
AS2 defines `context` as a **scoping/grouping key** and `inReplyTo` as the
field for **causal antecedents** (what this activity is responding to).
The full causal chain is recoverable: `in_reply_to` → Accept → `object_`
(inline `as_CaseProposal`). See ADR-0045.

### Step 2b: Case-actor rejects

When the case-actor service declines, it sends:

**`Reject(as_CaseProposal)`** — `object_` embeds the `as_CaseProposal`
inline (consistent with the Accept pattern; inline is preferred over URI-only
for rejection so the receiver has the full proposal context without a round-trip).

What *decides* the refusal is the `EvaluateCaseProposal` call-out point — see
[Admission Decision](#admission-decision-cp-05-002).

---

## Admission Decision (CP-05-002)

The service decides at one call-out point, `EvaluateCaseProposal` (Evaluator
shape, `CaseProposalCallOutBundle`). It is the only place a deployment can
express admission policy, and the DETERMINISTIC default admits — so an
unconfigured deployment behaves exactly as it did before the seam existed
(BT-23-001, BT-23-011). The adapter injects the bundle in
`inbox_port_factories._case_proposal_port_factory`, the same way it injects
`STATUS_AUTHORIZATION_PERMISSIVE`, so the seam is reachable in production rather
than test-only.

Three invariants make the refusal safe. Each was a real bug first; the general
form of each lives in [bt-pitfalls](bt-pitfalls.md).

**1. The decision is persisted before the side effect.**
`RecordProposalDeclineNode` writes `CaseProposalDeclineRecord` *before*
`EmitRejectCaseProposalNode` runs, and the accept arm is gated on that record's
absence (`CheckNoDeclineRecordNode`). Without that ordering a decline whose
`Reject` could not be built fell through the Selector into a **full accept**.
Everything in the refusal arm ahead of the record therefore **raises** rather
than returning `FAILURE`, because in a refusal arm `FAILURE` and `SUCCESS` can
both hand control to the permissive branch.

**2. Every guard is keyed on the proposal, never the report.** `report_id`
arrives as `request.inner_object_id` — the id of the report the *sender*
embedded — so it is sender-chosen, and two proposals may name one report. A
report-keyed "already answered?" guard therefore skips the gate for a proposal
that was never adjudicated, admitting it through the AC-1 duplicate-reuse path.
`CaseProposalAdmissionRecord`, written as the accept flow's *first* step, is the
proposal-keyed evidence that replaces it: it exists from before the case does,
which is what lets the guard recognise a half-built case as this proposal's.

The two decision records name the actor owed the answer `proposer_uri`, and the
`PendingCreateCaseActivity` marker names the actor owed the `Create`
`owner_uri` (CS-12-001); both were stored as `vendor_uri` before #4128, and a
row still carrying that key is refused with a reason naming the store reset
([datalayer-design](datalayer-design.md) § "Renaming a Stored Field").

**3. "Told them" comes from the record, not the outbox.** `outbox_pop` removes a
`Reject` on delivery while its stored copy remains, so a delivered refusal is
indistinguishable from one never queued. Reading the outbox therefore re-emits a
*fresh* `Reject` on every later delivery, without bound.
`CaseProposalDeclineRecord.reject_activity_id` records what was actually queued
and survives delivery, giving `CheckRejectAlreadyAnsweredNode` a third state:
declined-and-answered, versus declined-but-unanswered (which is recoverable and
re-emits).

**Known gap.** `CaseProposalDeclineRecord.reason` is read (into the `Reject`'s
`summary`) but nothing writes it: a call-out point signals refusal by returning
`FAILURE`, and BT-18-002 defines blackboard outputs only for the SUCCESS case, so
a refusal has no sanctioned channel for a payload. The same missing channel means
"backend unreachable" is indistinguishable from "policy declined", and the
resulting decline record is permanent. Tracked in
[#3446](https://github.com/CERTCC/Vultron/issues/3446).

Node locations: guards in
`vultron/core/behaviors/case/nodes/proposal_admission_conditions.py`, writes and
the emit in `.../proposal_admission_actions.py` (BTND-07-003).

---

## Wire Vocabulary: `as_CaseProposal`

`as_CaseProposal` is a new AS2 **Object** type (not an Activity) that extends
`as_VultronObject`. Required fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id_` | URI | Yes | Auto-generated unique proposal identifier |
| `attributed_to` | Actor URI | Yes | The proposing actor (report receiver, future CASE_OWNER) |
| `object_` | `as_VulnerabilityReport` or URI | Yes | The report for the case |
| `target` | URI | Yes | The prospective case-actor service URI |
| `summary` | str | No | Human-readable proposal description |
| `offer_id` / `offer_actor_id` | URI | No | Bare provenance of the `Offer(VulnerabilityReport)` that brought the report (CP-01-007) |
| `in_reply_to` | `as_Offer` | No | That Offer itself, carried whole (CP-01-008); must agree with the bare provenance and carry this report |

`in_reply_to` is how a Reporter's proposed embargo terms (`proposedEmbargo` on
the Offer, EP-04-004) reach the case-actor, which never saw the Offer; see
`notes/embargo-default-semantics.md` for the shortest-wins comparison they enter
at case creation (#3392, ADR-0096 amendment).

The CASE_OWNER's own terms travel the same way, on the envelope rather than the
proposal: this implementation requires the `actor` of `Create(as_CaseProposal)`
to be the proposing actor's full profile inline, carrying its `embargoPolicy`
when it has published one (CP-01-010). The protocol also permits a profile
reference the CASE_MANAGER dereferences (CP-01-009); this prototype requires the
inline form so case creation never fetches. The sender adapter puts its own
stored profile on the `Create`, and `refuse_malformed_case_proposal_envelope`
(`vultron/wire/as2/case_proposal_envelope.py`) refuses at the parse edge a
bare-URI `actor` and a profile whose `id` is not the proposal's
`attributed_to`. `CoreActor`'s own validator refuses a profile carrying another
actor's `embargoPolicy` (EP-01-001). The extractor hands the profile to core as
`proposer_profile`; how the tree reads the default from it is in
`notes/embargo-default-semantics.md`.

All classes in `vultron/wire/as2/vocab/objects/` use the `as_` prefix
(ARCH-14-001). The new type is `as_CaseProposal`; the bare name `CaseProposal`
refers to any eventual core domain model (if created).

---

## MessageSemantics Values

Three new values added to the `MessageSemantics` enum:

| Value | Pattern |
|-------|---------|
| `CREATE_CASE_PROPOSAL` | `Create(as_CaseProposal)` |
| `ACCEPT_CASE_PROPOSAL` | `Accept(as_CaseProposal)` |
| `REJECT_CASE_PROPOSAL` | `Reject(as_CaseProposal)` |

All three patterns MUST appear in `SEMANTIC_REGISTRY` before any
more-general patterns that share the same outer Activity type (SE-03-002).

---

## CaseActor Native Initialization (ADR-0041)

When the CASE_MANAGER accepts a proposal, `case_proposal_received_tree.py` MUST
perform the following natively — no back-fill, no prologue:

1. Create `VulnerabilityCase` with `attributed_to` = the proposing actor (the
   report receiver, who is the case owner; CP-09-001). The CASE_MANAGER records
   that it *created* the case as the `actor` of `Create(VulnerabilityCase)`, not
   in `attributed_to`. The genesis hash follows `attributed_to` too: the case's
   own validator computes it from the owner, so the CASE_MANAGER passes none and
   the case hashes as if the owner had created it (CLP-08-002, ADR-0117; see
   [case-ledger-authority](case-ledger-authority.md))
2. Add the report receiver as `CASE_OWNER` participant at `RM.RECEIVED`
3. Add reporter as participant at `RM.ACCEPTED`
4. Initialize default embargo
5. Commit canonical ledger entries (`create_case`, `add_report_to_case`,
   `add_participant_status_to_participant` × N, `add_case_status_to_case`)
6. Emit `Accept(as_CaseProposal)` with `result=case_id`
7. Emit `Create(VulnerabilityCase)` with inline participant objects so that
   `store_embedded_participants` seeds them correctly
   on the receiver's replica

The `Create(VulnerabilityCase)` payload MUST embed participant objects inline
(not bare IDs) so the receiver can seed its replica without a DataLayer round-trip
to the CaseActor.

### Removed nodes (ADR-0041)

The following nodes are **removed** from the receiver's
`receive_report_case_tree.py` and must not be re-added:

| Removed node | Reason |
|---|---|
| `CreateCaseNode` | CaseActor creates the case |
| `CreateCaseOwnerParticipant` | CaseActor adds receiver as participant |
| `InitializeDefaultEmbargoNode` | CaseActor initializes embargo |
| `CreateCaseActivity` / `UpdateActorOutbox` | CaseActor emits `Create(VulnerabilityCase)` |
| `CreateCaseActorNode` | CaseActor is a pre-existing service, not spawned by the receiver |
| `SendOfferCaseManagerRoleNode` *(deleted, issue #2429)* | CaseActor adds itself as `CASE_MANAGER` natively — replaced by `OFFER_CASE_PARTICIPANT_ROLE` (ADR-0039) |
| `WritePrologueLedgerEntriesNode` | Back-fill replaced by native CaseActor init |

### Corrected receiver tree shape (ADR-0041)

`receive_report_case_tree.py` becomes:

```text
ReceiveReportCaseBT (Sequence)
├─ CheckAutoCaseCreationEnabledNode
└─ ReceiveReportCaseSelector (Selector)
   ├─ CheckProposalAlreadySentForReport    # idempotency
   └─ ReceiveReportProposalFlow (Sequence)
      ├─ WritePendingReportCaseLinkNode      # VultronReportCaseLink(status=PENDING_PROPOSAL)
      └─ ProposeCaseToActorNode              # Create(as_CaseProposal) → CaseActor
```

No `VulnerabilityCase`, no participants, no embargo created by the report receiver.

## BT Integration: `ProposeCaseToActorNode`

`ProposeCaseToActorNode` sends `Create(as_CaseProposal)` to the CaseActor
service. The CaseActor service URI comes from
`ActorConfig.case_actor_service_url` (CP-08-001 through CP-08-003).

---

## Received-Side Use Cases

Three received-side use cases are required:

| Use Case | Actor | Handles |
|----------|-------|---------|
| `CreateCaseProposalReceivedUseCase` | Case-actor service | `Create(as_CaseProposal)` arriving at case-actor inbox |
| `AcceptCaseProposalReceivedUseCase` | Report receiver | `Accept(as_CaseProposal)` arriving at receiver inbox |
| `RejectCaseProposalReceivedUseCase` | Report receiver | `Reject(as_CaseProposal)` arriving at receiver inbox |

All three must be registered as the `use_case_class` of their `SEMANTIC_REGISTRY`
entry, keyed by the corresponding `MessageSemantics` value, so that they appear
in the mapping returned by `use_case_map()`.

---

## Relationship to Related Issues

| Issue | Relationship |
|-------|-------------|
| #810 | **Blocked by this**: demo routing to dedicated case-actor container requires the CaseProposal protocol to be in place before `CreateCaseActorNode` can be adapted for the demo layer. Note: the current FV demo passes all convergence invariants (all 26 invariants PASS as of #1025 review), confirming that #810 is architectural improvement work rather than a blocking bug. |
| #811 | Spec + ADR for CaseActor dynamic spawning — a broader concern; CaseProposal is a prerequisite input. |
| #812 | Implementation of CaseActor dynamic spawning — blocked by #811 and this work. |

---

## CaseActor Service URL Configuration

**Source**: Issue #1633 (2026-07-23).

The CaseActor's identity is `{case_actor_service_url}/actors/case-actor` — one per
container, with **no per-case slug**. `case_actor_identity()` in
`vultron/core/behaviors/case/case_actor_identity.py` is the single place it is
computed. The URL source MUST be `ActorConfig.case_actor_service_url`
(`get_config().actor.case_actor_service_url`); it MUST NOT be derived from
`server_base_url` on the blackboard (that would hard-wire a co-location
assumption that breaks multi-container topologies).

### Why there is no per-case slug (#1872)

The identity used to be `.../actors/case-actor-{_derive_case_slug(report_id)}`,
and that was unhostable by construction. The *sender* computed it, so no container
had registered it, and `POST /actors/case-actor-<slug>/inbox/` answered a
permanent **404** — the CaseProposal round-trip never began.

Provisioning it in advance is impossible, not merely awkward. The slug depends on a
report the receiver has not seen, so it is not computable until the reporter's
`submit-report` trigger returns — and that trigger's own outbox drain has by then
already delivered the `Offer`, the receiver has already proposed, and the 404 has
already happened. Observed directly: the 404 logged *before* the provisioning
intended to prevent it.

A CaseActor is a participant wearing the `CVDRole.CASE_MANAGER` hat, not a per-case
object. An actor participates in many cases, and which case a message concerns
travels in `activity.context` — so the slug carried nothing the payload lacked.
This also subsumes the eventual one-process-per-case direction: such a process gets
its own first-class actor identity, not a slug suffix on somebody else's.

Normative: CP-04-003, BT-10-002.

### Being addressable also means writing to the right store

A stable identity is necessary but not sufficient. `POST /actors/{slug}/inbox/`
resolves the actor from the store that slug names (ADR-0073), so the record has to
be in the **CaseActor's own** store. A copy in the sending actor's store is an
address-book entry — knowledge of a peer — and publishes no endpoint. Writing only
that one is the other half of the same 404. Normative: CP-04-004.

In Docker Compose deployments, actors that create cases MUST supply:

```yaml
environment:
  - VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL=http://case-actor:7999/api/v2
```

This is a TEMPORARY per-actor config field pending a proper actor-ID-to-endpoint
resolution mechanism (issues #1189, #1092). Normative requirements: CP-08-001
through CP-08-003.

### Pitfall: `server_base_url` is NOT the CaseActor service URL

The co-location assumption manifests as:

```python
# WRONG — twice over: the container's own base URL, and a per-case slug
server_base_url = _resolve_server_base_url(self.blackboard)
case_actor_id = f"{server_base_url}/actors/case-actor-{case_slug}"
```

The base URL is wrong because it silently works in single-container demos and
mis-routes in multi-container topologies (the receiver proposes to itself). The slug
is wrong because it is unhostable at all — see above. The fix:

```python
# CORRECT — one helper, config-sourced, no slug
from vultron.core.behaviors.case.case_actor_identity import case_actor_identity

case_actor_id = case_actor_identity()
if case_actor_id is None:
    self.logger.error("%s: case_actor_service_url not configured", self.name)
    return Status.FAILURE
```

`case_actor_identity()` returns `None` rather than substituting a default, because
a guessed base URL reproduces exactly the unresolvable-identity failure.

---

## Durable-Delivery Marker (CP-05-005)

The case-actor's accepted path involves two sequenced outbound activities
(`Accept(CaseProposal)` then `Create(VulnerabilityCase)`). If the second
delivery fails after the first succeeds, the report receiver receives an Accept with
no corresponding case announcement.

To recover from this, a `PendingCreateCaseActivity` marker is written to
the DataLayer **after** `Accept` is sent and **before** `Create` is
attempted (implemented in `WriteCreateCaseMarkerNode` in
`vultron/core/behaviors/case/nodes/proposal_retry_marker.py`). The marker captures the proposal ID,
case-actor ID, receiver URI, and the pre-constructed
`Create(VulnerabilityCase)` payload. It is deleted on successful
`Create` delivery, so only failed deliveries leave a marker.

Because the marker is gone once the `Create` is queued, it cannot tell a
redelivered proposal that the case was already announced. The `Create`'s
id is therefore derived from the proposal
(`PendingCreateCaseActivity.create_activity_id()`), not minted. A redelivery
that finds that activity already stored writes no marker and queues nothing,
whether the first delivery succeeded or a later leaf failed after the marker
was cleared (#4146). The proposal id is the sender's, so the stored activity
is checked, not just found: `announced_case_id()` (in
`proposal_retry_marker.py`) refuses anything but a `Create` naming a case, and
`WriteCreateCaseMarkerNode` fails if that case is not the one it just built.
A sender that reused a proposal id for another report would otherwise get a
case that is never announced while the tree reports SUCCESS. Reading the store
is sound only because the marker is cleared *after* the enqueue: while it
exists, `CheckMarkerExistsNode` short-circuits and the retry runner owns
recovery, so "Create stored, no marker" means "queued".

### Retry Runner (AC-2: startup-scan option)

`vultron/adapters/driving/fastapi/pending_retry.py` provides
`retry_pending_create_case_activities()`, called once in the FastAPI
application lifespan before the server starts accepting requests.

The runner uses **option (a): on-startup scan**:

1. Get all actor-scoped DataLayers from the process-level cache
   (``get_all_actor_datalayers()``).
2. **Supplement** by scanning each *hosted actor's own* store for persisted
   ``PendingCreateCaseActivity`` markers.  Any ``case_actor_id`` values found
   that are not already in the cache get a DataLayer via ``clone_for_actor()``.
   This step is critical on crash/restart: the process cache is empty, but the
   per-actor SQLite files still hold the obligation rows.

   There is no shared/unscoped DataLayer to scan (ADR-0073, DL-07-002), which is
   why the scan enumerates hosted actors — ``hosted_actor_ids()`` derives them
   from the per-actor stores that exist, so it also finds CaseActors created at
   runtime that appear in no config file.
3. For each actor DataLayer, scan for markers, reconstruct the stored
   ``Create(VulnerabilityCase)`` payload **verbatim** using the marker's
   ``create_activity_payload`` (never re-constructing the activity), and
   re-enqueue to the actor's outbox.
4. Delete the marker on success.

Using the stored payload (not a freshly constructed activity) preserves
the original ``id_``, which is essential: the retry runner's outbox
idempotency check looks for that specific ``id_``.  A fresh ``id_``
would bypass the check and cause a duplicate delivery after crash/restart.

### The Same Shape for the Creation-Time Revision Relay (EP-04-011)

The accept flow owes one more delivery on a contested creation: the
`Invite(EmbargoEvent)` that relays the shortest-wins loser to the winner
(EP-04-011). Creation-time initialization runs once per case (EP-04-012), so
nothing on a redelivered proposal would register the revision again, and a relay
that failed would be lost. `InitializeCreationEmbargoNode` therefore writes
a `PendingCreationTimeRevisionRelay` marker in the same commit that registers the
revision, and `RelayCreationTimeRevisionNode` reads it,
relays, indexes, and deletes it; a failure after the write keeps it. The same
lifespan scan calls `retry_pending_creation_time_revision_relays()` after the
Create retry, which re-runs the relay node for each marker's case behind the
CASE_MANAGER gate, and sends nothing until the case's genesis `create_case`
ledger entry is committed (CM-14-007). A later delivery of a proposal for the
case also completes it, since its accept arm reaches the relay again — but not
while a `PendingCreateCaseActivity` marker exists, because
`CheckMarkerExistsNode` short-circuits that redelivery. It is a separate record type rather than a field on an existing one, so
no existing persisted shape changes. See
[embargo-default-semantics.md](embargo-default-semantics.md) for the relay
itself (#4121).

---

## Duplicate-Proposal Handling (CP-05-006)

At-least-once delivery and network retries mean the same
`Create(as_CaseProposal)` can arrive multiple times. Since the admission gate
landed, `create_case_proposal_received_tree` is a **four-arm Selector** — in
order: the in-flight marker, the already-declined answer, the admission
decision, and the accept flow. See
[Admission Decision](#admission-decision-cp-05-002) below for the two refusal
arms; the two guards that carry duplicate handling on the accept side are:

**AC-3 guard** (`CheckMarkerExistsNode`): if a
`PendingCreateCaseActivity` marker exists, `Accept` was already sent and
`Create(VulnerabilityCase)` delivery is still pending. The retry runner
owns recovery; the duplicate is silently dropped.

**Same proposal redelivered** (CP-05-006, ASK-08-001): the duplicate is keyed on
the *proposal id*. The case-actor re-sends the stored `Accept(as_CaseProposal)`
unchanged, with its original id, so it reads as the first acceptance arriving
late rather than a second decision, and it creates no second case
(ASK-08-002). The reference implementation does this: the `Accept` id is derived
from the proposal, and a duplicate queues the stored `Accept` again unless it is
still pending in the outbox (#4215). The proposer-side deadline (CP-05-007) is
still open (#2890).

**Different proposal id, same report** (CP-05-008): a new request, because the
requester tracks each proposal as its own ask (CP-05-007) and may already have
expired the first. It is adjudicated like any proposal and answered with its
*own* `Accept` or `Reject`; the stored `Accept` of the earlier proposal is not
sent, since it answers a proposal the requester may have dropped. The flow
below (`LoadExistingCaseNode` → `EmitAcceptCaseProposalNode`) is this path:

- the existing case is reused only when the proposer owns it; a different
  proposer naming the same report gets a case of its own (CBT-06-002), because
  the report id is chosen by the sender and a report-only lookup would add the
  second proposer to someone else's case. Today `LoadExistingCaseNode` looks up
  by report alone, so this is not yet true (strict xfail,
  `test_second_proposer_for_an_accepted_report_gets_its_own_case`, #3977);
- `object_` = inline `as_CaseProposal` (CP-05-003);
- **`result` = URI of the reused `VulnerabilityCase`**, so the requester can
  correlate it without waiting for a second `Create(VulnerabilityCase)`, which
  the case-actor does not send again (CP-05-005, #4146).

For first-time proposals, `EmitAcceptCaseProposalNode` also sets
`result=case_id` (the newly-created case URI). This is consistent: the
`result` of an Accept always names the `VulnerabilityCase` the proposal
produced (or reused).

**Reusing the case means reusing its embargo.** The AC-1 flow runs the same
native-initialization nodes as a first proposal, so each of them has to be a
no-op on a case that already has what it would create. Participants and
ledger entries were (their tests are in `TestADR0041Idempotency`); the embargo
subtree was not until #3393: `InitializeDefaultEmbargoNode`'s creation arm
re-ran on the existing case, minting an orphan `EmbargoEvent` on the default
path and registering the losing candidate as a *second* pending revision on
the contested one (EP-04-003) — one revision per delivery of the same report.
`CaseEmbargoAlreadyInitializedNode` is now the subtree's first arm: an EM
state other than `NONE` means initialization already ran (EP-04-012, #4019;
the active-embargo reference it first read is cleared by termination). The
receiver stops feeding the duplicate too — `CheckProposalAlreadySentForReport`
treats an answered `ReportCaseLink` (case linked) as "already proposed", so a
re-delivered Offer does not re-propose. What the case-actor answers with is
settled above: the stored `Accept` for the same proposal, a fresh one for a new
proposal id.

**What "duplicate" means here.** An exact redelivery of the same proposal id —
at-least-once delivery, or the receiver asking again because the `Accept` was lost
(CP-05-006, ADR-0080, decided in #3977). It does *not* mean a second proposal for
the same report, which is a new request (CP-05-008), and it does not mean a second
report that describes the same vulnerability; that is a report-management question
(RMB-11-002: duplicate reports are not invalid) and never reaches this tree as a
"duplicate". Three consequences follow.

- The reuse branch must leave the existing case's state alone, including its
  embargo whatever EM state it is in (EP-04-012;
  `notes/embargo-default-semantics.md` § "Initialization Runs Once Per Case").
- `LoadExistingCaseNode` keys on the *report*, which is the wrong key for both of
  the branch's real jobs: answering the same proposal again, and finishing the
  same proposal's half-built case. Those two belong on the *proposal*. The
  per-proposal `CaseProposalAdmissionRecord` is the place to carry the case it
  made and the id of the `Accept` it queued, the way `CaseProposalDeclineRecord`
  carries `reject_activity_id`: one indexed read, in place of the scan of every
  stored `Accept` that `find_activity_for_proposal` does today.
- A report-only lookup is also wrong for a *different* proposer, who is owed a
  case of its own (CBT-06-002), so a lookup by report has to take the proposer
  into account (CP-05-008).

### Implementation: `VultronAccept.result`

`vultron.core.models.activity.VultronAccept` carries a `result: str | None`
field. `EmitAcceptCaseProposalNode` reads `case_id` from the py\_trees
blackboard (written earlier by `LoadExistingCaseNode` or
`CreateCaseFromProposalNode`) and sets `result=case_id` on the activity
before persisting it to the DataLayer and outbox.

---

## Exchange Demo: Discovering the Canonical Case

After `validate-report` runs in an exchange demo, `ProposeReportCaseToActorNode`
fires automatically and the CaseActor creates the canonical `VulnerabilityCase`.
Do NOT call `create_case_activity` to create a receiver-local case — that produces
a second, unlinked case with no participants.

**Pattern for exchange demo setup:**

```python
def _find_canonical_case(client) -> dict:
    cases = client.get("/datalayer/VulnerabilityCases/").json()
    for case_id, case in cases.items():
        if case.get("case_participants"):
            return case
    raise AssertionError("No canonical case found after validate-report")
```

`GET /datalayer/VulnerabilityCases/` returns a `dict[str, dict]` keyed by object
ID. The canonical case is the one with `case_participants` populated.

A receiver-local case created by calling `create_case_activity` anyway is broken in
three distinct ways, none of which raise:

- it has no `ReportCaseLink`, so `create_case_received` skips it;
- it gets no participants, because `ProposeCaseToActorNode` finds no linked
  report; and
- it is entirely distinct from the canonical case the CaseActor owns, so every
  later assertion reads the wrong object.

The canonical case is always in the shared DataLayer after `validate-report`,
even in single-backend test environments where `TestClientRouter` does not
register the CaseActor's delivery address (`https://vultron.example`) — the
CaseActor's `Create(VulnerabilityCase)` delivery to the receiver is silently dropped
there, but the case itself is in the DataLayer.

Source: ISSUE-1994
