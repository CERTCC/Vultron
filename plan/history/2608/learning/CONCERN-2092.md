---
source: CONCERN-2092
timestamp: '2026-08-26T18:21:02.322500+00:00'
title: sentinel PXA authority model — conservative gate defaults for StatusAdoptionGate
  and EmbargoTeardownAuthorizationGate
type: learning
---

## Concern

CONCERN-2092 identified that `StatusAdoptionGate` and `EmbargoTeardownAuthorizationGate`
both defaulted to `AlwaysSucceed`, creating a protocol-exploitable channel: a hostile or
malfunctioning sentinel actor admitted as OBSERVER could force PXA state adoption and
embargo teardown without Case Owner approval.

## Decision

Flip both gate defaults from `AlwaysSucceed` to `RequireCaseOwnerApproval` — an Evaluator
that performs an Offer/Accept/Reject round-trip with the Case Owner using existing AS2
vocabulary. Permissive backends (e.g., `AlwaysSucceed`) remain valid MAY configurations
for trusted-participant or demo deployments but MUST be explicitly configured.

`RequireCaseOwnerApproval` is the default because:

- The opposite of "always allow" is not "always block" — it is "ask the owner"
- The pattern recurs across status updates, invitation suggestions, and embargo proposals
- A reusable tree factory with parameters should be designed (impl issue #2676)

## Key artifacts

- ADR-0076: `Security-Significant Call-Out Gates Default to RequireCaseOwnerApproval`
  — new ADR establishing the project-wide exception to ADR-0025's ceiling/floor rule
- ADR-0025 amended in-place: security-significant gate exception paragraph added
- ADR-0046 revised in-place: Consequences section and gate definition blocks updated
- Specs RSH-07-001..003 added to `specs/received-status-handling.yaml`
- RSH-02-002 flipped from MUST be `AlwaysSucceed` → MUST be `RequireCaseOwnerApproval`
- Notes `received-status-authorization.md` and `call-out-configuration.md` updated

## Implementation

- #2675 (size:M): Flip `StatusAuthorizationCallOutBundle` defaults + add `RequireCaseOwnerApproval` tree factory
- #2676 (size:L): Audit all call-out gates for security-significant permissive defaults and flip them

Both wired as sub-issues of epic #1935 (Protocol authority & lifecycle semantics).

## PR

<https://github.com/CERTCC/Vultron/pull/2674>
