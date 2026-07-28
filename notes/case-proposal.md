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
  - specs/semantic-extraction.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/case-communication-model.md
  - notes/bt-integration.md
relevant_packages:
  - vultron/wire/as2/vocab/objects
  - vultron/core/models/events
  - vultron/core/use_cases/received
  - vultron/core/behaviors/case
---

# CaseProposal Protocol

**Source**: 2026-06-22 grill-me planning session, issue #1081.
Normative requirements: `specs/case-proposal.yaml` (CP-01 through CP-07).
ADR: `docs/adr/0023-case-proposal-protocol.md`.

---

## Motivation

`CreateCaseActorNode` currently creates the CaseActor locally in the vendor's
DataLayer. When the case-actor service is external (issue #810), the vendor
needs a way to tell the case-actor service about a new case.

Sending `Create(VulnerabilityCase)` from the vendor is not correct. In
ActivityStreams, `Create(X)` means "I created X." The vendor is not the
authoritative creator of the case — the case-actor service is. Using the
vendor as `actor` on a `Create(VulnerabilityCase)` violates this semantics.

The `CaseProposal` object provides a clean solution: the vendor proposes that
the case-actor service create the case, while the case-actor service does the
actual creation.

---

## Protocol Flow

```text
Vendor                              CaseActor Service
  |                                       |
  | --- Create(CaseProposal) -----------> |
  |         actor: vendor URI             |
  |         object_: as_CaseProposal      |
  |                                       |
  |           [evaluates proposal]        |
  |                                       |
  | <-- Accept(CaseProposal) ----------- |  (happy path)
  |         actor: case-actor URI         |
  |         object_: as_CaseProposal      |
  |                                       |
  | <-- Create(VulnerabilityCase) ------- |
  |         actor: case-actor URI         |
  |         context: Accept URI           |
  |                                       |
  |    -- OR --                           |
  |                                       |
  | <-- Reject(CaseProposal) ----------- |  (rejection path)
  |         actor: case-actor URI         |
  |         object_: as_CaseProposal      |
```

### Step 1: Vendor sends `Create(as_CaseProposal)`

The vendor creates an `as_CaseProposal` object containing:

- `id_`: auto-generated URI for the proposal
- `attributed_to`: the vendor actor URI
- `object_`: inline or URI-referenced `as_VulnerabilityReport`
- `target`: the case-actor service URI
- `summary` (optional): human-readable description

The vendor then sends `Create(as_CaseProposal)` to the case-actor service's
inbox, with `actor=vendor_uri`.

### Step 2a: Case-actor accepts (happy path)

When the case-actor service decides to create the case, it sends **two**
activities back to the vendor:

1. **`Accept(as_CaseProposal)`** — acknowledgment that the proposal was
   accepted. `object_` embeds the `as_CaseProposal` inline.

2. **`Create(VulnerabilityCase)`** — the actual case creation announcement.
   - `actor` = case-actor URI (preserving AS2 "I created this" semantics)
   - `context` = URI of the `Accept(CaseProposal)` activity (proximate cause)

Setting `context` to the Accept URI (not the CaseProposal URI directly) was
chosen because the `Accept` is the proximate causal decision. The proposal
is already embedded in the Accept's `object_`, so causal traceability is
preserved transitively.

### Step 2b: Case-actor rejects

When the case-actor service declines, it sends:

**`Reject(as_CaseProposal)`** — `object_` embeds the `as_CaseProposal`
inline (consistent with the Accept pattern; inline is preferred over URI-only
for rejection so the vendor has the full proposal context without a round-trip).

---

## Wire Vocabulary: `as_CaseProposal`

`as_CaseProposal` is a new AS2 **Object** type (not an Activity) that extends
`VultronAS2Object`. Required fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id_` | URI | Yes | Auto-generated unique proposal identifier |
| `attributed_to` | Actor URI | Yes | The vendor/proposer actor URI |
| `object_` | `as_VulnerabilityReport` or URI | Yes | The report for the case |
| `target` | URI | Yes | The prospective case-actor service URI |
| `summary` | str | No | Human-readable proposal description |

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

All three patterns MUST appear in `SEMANTICS_ACTIVITY_PATTERNS` before any
more-general patterns that share the same outer Activity type (SE-03-002).

---

## BT Integration: `ProposeCaseToActorNode`

A new BT leaf node `ProposeCaseToActorNode` is responsible for sending
`Create(as_CaseProposal)` to the case-actor service. It is distinct from
`CreateCaseActorNode`.

### Node roles — do not conflate

| Node | Responsibility |
|------|----------------|
| `CreateCaseActorNode` | Registers the case-actor service as an actor resource in the local DataLayer. Creates the actor identity, not the case. |
| `ProposeCaseToActorNode` | Sends `Create(as_CaseProposal)` to the already-registered case-actor service. Initiates the case initialization protocol. |

`ProposeCaseToActorNode` is wired into the case-creation BT tree **after**
`CreateCaseActorNode` succeeds — the actor must exist before the proposal can
be sent to it.

---

## Received-Side Use Cases

Three received-side use cases are required:

| Use Case | Actor | Handles |
|----------|-------|---------|
| `CreateCaseProposalReceivedUseCase` | Case-actor service | `Create(as_CaseProposal)` arriving at case-actor inbox |
| `AcceptCaseProposalReceivedUseCase` | Vendor | `Accept(as_CaseProposal)` arriving at vendor inbox |
| `RejectCaseProposalReceivedUseCase` | Vendor | `Reject(as_CaseProposal)` arriving at vendor inbox |

All three must be registered in the dispatcher's `USE_CASE_MAP` keyed by the
corresponding `MessageSemantics` value.

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

`ResolveCaseActorUrlsNode` derives the CaseActor service identity
by combining `case_actor_service_url` from `ActorConfig` with a
per-case slug. The URL source MUST be `ActorConfig.case_actor_service_url`
(`get_config().actor.case_actor_service_url`); it MUST NOT be derived from
`server_base_url` on the blackboard (that would hard-wire a co-location
assumption that breaks multi-container topologies).

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
# WRONG — uses the running container's own base URL
server_base_url = _resolve_server_base_url(self.blackboard)
case_actor_id = f"{server_base_url}/actors/case-actor-{case_slug}"
```

This silently works in single-container demos but produces a mis-routed
proposal in multi-container topologies (the Vendor proposes to itself
instead of the dedicated CaseActor container). The fix:

```python
# CORRECT — reads from explicit config
from vultron.config import get_config
cfg = get_config().actor
if cfg.case_actor_service_url is None:
    self.logger.error("%s: case_actor_service_url not configured", self.name)
    return Status.FAILURE
base_url = str(cfg.case_actor_service_url).rstrip("/")
case_actor_id = f"{base_url}/actors/case-actor-{case_slug}"
```

---

## Open Questions

None — all design decisions were resolved in the planning session.
See `docs/adr/0023-case-proposal-protocol.md` for the alternatives evaluated.

---

## Durable-Delivery Marker (CP-05-005)

The case-actor's accepted path involves two sequenced outbound activities
(`Accept(CaseProposal)` then `Create(VulnerabilityCase)`). If the second
delivery fails after the first succeeds, the vendor receives an Accept with
no corresponding case announcement.

To recover from this, a `PendingCreateCaseActivity` marker is written to
the DataLayer **after** `Accept` is sent and **before** `Create` is
attempted (implemented in `vultron/core/behaviors/case/
case_proposal_received_tree.py`). The marker captures the proposal ID,
case-actor ID, vendor URI, and the pre-constructed
`Create(VulnerabilityCase)` payload. It is deleted on successful
`Create` delivery, so only failed deliveries leave a marker.

### Retry Runner (AC-2: startup-scan option)

`vultron/adapters/driving/fastapi/pending_retry.py` provides
`retry_pending_create_case_activities()`, called once in the FastAPI
application lifespan before the server starts accepting requests.

The runner uses **option (a): on-startup scan**:

1. Get all actor-scoped DataLayers from the process-level cache
   (``get_all_actor_datalayers()``).
2. **Supplement** by scanning the shared (unscoped) DataLayer for
   persisted ``PendingCreateCaseActivity`` markers.  Any ``case_actor_id``
   values found that are not already in the cache get a fresh actor-scoped
   DataLayer via ``clone_for_actor()``.  This step is critical on
   crash/restart: the process cache is empty, but the SQLite file still
   holds the obligation rows.
3. For each actor DataLayer, scan for markers, reconstruct the stored
   ``Create(VulnerabilityCase)`` payload **verbatim** using the marker's
   ``create_activity_payload`` (never re-constructing the activity), and
   re-enqueue to the actor's outbox.
4. Delete the marker on success.

Using the stored payload (not a freshly constructed activity) preserves
the original ``id_``, which is essential: the retry runner's outbox
idempotency check looks for that specific ``id_``.  A fresh ``id_``
would bypass the check and cause a duplicate delivery after crash/restart.

---

## Duplicate-Proposal Handling (CP-05-006)

At-least-once delivery and network retries mean the same
`Create(as_CaseProposal)` can arrive multiple times. The idempotency
tree (`create_case_proposal_received_tree`) has two guards:

**AC-3 guard** (`_CheckMarkerExistsNode`): if a
`PendingCreateCaseActivity` marker exists, `Accept` was already sent and
`Create(VulnerabilityCase)` delivery is still pending. The retry runner
owns recovery; the duplicate is silently dropped.

**AC-1 / AC-2 flow** (`_LoadExistingCaseNode` → `_EmitAcceptCaseProposalNode`):
if no in-flight marker exists but a `VulnerabilityCase` already exists for
the same report, the tree reuses the existing case (AC-1). It then sends a
new `Accept(as_CaseProposal)` (AC-2) with:

- `object_` = inline `as_CaseProposal` (CP-05-003)
- **`result` = URI of the existing `VulnerabilityCase`** (CP-05-006 AC-2)

The `result` field is where the duplicate Accept carries the existing-case
reference so the vendor can correlate it to the already-created case without
waiting for a second `Create(VulnerabilityCase)`.

For first-time proposals, `_EmitAcceptCaseProposalNode` also sets
`result=case_id` (the newly-created case URI). This is consistent: the
`result` of an Accept always names the `VulnerabilityCase` the proposal
produced (or reused), regardless of whether the proposal is a first send or a
retry.

### Implementation: `VultronAccept.result`

`vultron.core.models.activity.VultronAccept` carries a `result: str | None`
field. `_EmitAcceptCaseProposalNode` reads `case_id` from the py\_trees
blackboard (written earlier by `_LoadExistingCaseNode` or
`_CreateCaseFromProposalNode`) and sets `result=case_id` on the activity
before persisting it to the DataLayer and outbox.
