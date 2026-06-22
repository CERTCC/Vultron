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
| #810 | **Blocked by this**: demo routing to dedicated case-actor container requires the CaseProposal protocol to be in place before `CreateCaseActorNode` can be adapted for the demo layer. Note: the current two-actor demo passes all convergence invariants (all 26 invariants PASS as of #1025 review), confirming that #810 is architectural improvement work rather than a blocking bug. |
| #811 | Spec + ADR for CaseActor dynamic spawning — a broader concern; CaseProposal is a prerequisite input. |
| #812 | Implementation of CaseActor dynamic spawning — blocked by #811 and this work. |

---

## Open Questions

None — all design decisions were resolved in the planning session.
See `docs/adr/0023-case-proposal-protocol.md` for the alternatives evaluated.
