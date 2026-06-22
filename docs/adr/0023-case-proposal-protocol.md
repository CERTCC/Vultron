---
status: accepted
date: 2026-06-22
deciders: [adh, Copilot]
---

# ADR-0023: Introduce `CaseProposal` for Distributed Case Actor Initialization

## Context and Problem Statement

When a vendor needs to request case initialization at a dedicated case-actor
service (#810), how should it communicate that request while preserving
ActivityStreams 2.0 semantics?

`Create(VulnerabilityCase)` from the vendor is not semantically correct:
the AS2 specification states that `Create` means "I (the `actor`) created this
object." The vendor is not the authoritative creator of the case — the
case-actor service is. Using the vendor as `actor` on
`Create(VulnerabilityCase)` would misrepresent authorship and undermine the
trust model that relies on the case-actor as the single authoritative source
for case identity and state.

## Decision Drivers

- Preserve AS2 "I created this" semantics: only the authoritative creator
  SHOULD be the `actor` on `Create(X)`.
- Keep case initialization in-protocol (no out-of-band provisioning calls).
- Allow the case-actor service to evaluate and reject proposals (insufficient
  info, duplicate, out-of-scope, policy).
- Maintain clear causal traceability from proposal through acceptance to case
  creation.

## Considered Options

1. **`CaseProposal` negotiation object** (chosen): vendor sends
   `Create(CaseProposal)` → case-actor sends `Accept(CaseProposal)` then
   `Create(VulnerabilityCase, actor=case-actor)`.

2. **`Offer(VulnerabilityCase)` semantics**: vendor sends
   `Offer(VulnerabilityCase)` → case-actor sends `Accept(Offer)` then
   `Create(VulnerabilityCase)`.

3. **Vendor sends `Create(VulnerabilityCase)` anyway**: the case-actor service
   overwrites/supersedes the vendor-created case with its own authoritative
   version.

4. **Out-of-band provisioning call**: vendor calls a REST API on the
   case-actor service directly (outside the Vultron inbox/outbox protocol).

## Decision Outcome

**Chosen option: CaseProposal negotiation object (#1).**

A dedicated `as_CaseProposal` wire object lets the vendor request initialization
while preserving correct AS2 semantics. The vendor `actor` on
`Create(CaseProposal)` accurately reflects that the vendor created the
*proposal*, not the case. The case-actor creates the case and correctly sets
itself as `actor` on the subsequent `Create(VulnerabilityCase)`.

The full positive-path flow:

```text
Vendor → Create(as_CaseProposal) → CaseActor inbox
CaseActor → Accept(as_CaseProposal) → Vendor inbox
CaseActor → Create(VulnerabilityCase, actor=CaseActor, context=Accept URI) → Vendor inbox
```

Setting `context` on `Create(VulnerabilityCase)` to the `Accept(CaseProposal)`
URI was preferred over the `CaseProposal` URI directly, because the Accept is
the proximate causal decision. The proposal is embedded inline in the Accept's
`object_`, so full causal traceability is preserved transitively.

### Consequences

- Good: AS2 `actor` semantics are preserved end-to-end.
- Good: The case-actor service retains full authority over case identity.
- Good: Rejection is naturally expressed as `Reject(CaseProposal)`.
- Good: Fully in-protocol; no out-of-band REST calls.
- Neutral: Adds three new `MessageSemantics` values and three received-side
  use cases.
- Neutral: The two-activity positive response (`Accept` then `Create`) adds
  a message, but both are semantically distinct and necessary.

## Pros and Cons of the Options

### Option 1: `CaseProposal` negotiation object (chosen)

- Good: Unambiguous AS2 authorship on all activities.
- Good: Explicit accept/reject lifecycle; case-actor policy is expressible.
- Good: Extends naturally to future negotiation semantics.
- Neutral: New vocabulary type required.

### Option 2: `Offer(VulnerabilityCase)` semantics

- Good: Reuses existing `Offer`/`Accept` vocabulary without a new type.
- Bad: `Offer(VulnerabilityCase)` is already overloaded in Vultron for
  report delivery semantics (`VP` spec). Re-using it for case initialization
  would create ambiguous routing.
- Bad: The case inside an Offer is not yet the authoritative case; naming it
  `VulnerabilityCase` before it exists is misleading.

### Option 3: Vendor sends `Create(VulnerabilityCase)` anyway

- Bad: Direct AS2 semantics violation: the vendor cannot be `actor` on
  `Create(VulnerabilityCase)` if it is not the authoritative creator.
- Bad: The case-actor overwrite model is fragile; two `Create` activities for
  the same case from different actors would require a complex resolution
  protocol.

### Option 4: Out-of-band provisioning

- Bad: Breaks the Vultron protocol model (all coordination in-protocol).
- Bad: Requires a separate REST API on the case-actor service, increasing
  coupling and deployment complexity.
- Bad: No standardized reject/accept lifecycle.

## More Information

- Source issue: #1081
- Blocked-by: this ADR and its implementation (issues planned in #1081
  comments)
- Blocks: #810 (demo routing to dedicated case-actor service), #811 (spawning
  spec/ADR), #812 (spawning implementation)
- Notes: `notes/case-proposal.md`

Generated spec requirements: `specs/case-proposal.yaml` CP-01 through CP-07.
