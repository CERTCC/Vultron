---
status: accepted
date: 2026-08-26
deciders: Allen D. Householder
consulted: Claude Sonnet 4.6
informed: []
---

# Security-Significant Call-Out Gates Default to `RequireCaseOwnerApproval`

## Context and Problem Statement

The two-gate authorization model (ADR-0046) places a configurable Evaluator
call-out at `StatusAdoptionGate` (`CaseOwnerApprovesStatusUpdate`) and at
`EmbargoTeardownAuthorizationGate`. Both gates defaulted to `AlwaysSucceed`,
inheriting the ADR-0025 ceiling/floor rule that maps a stochastic node with
`p ≥ 0.5` to `AlwaysSucceed` in DETERMINISTIC mode.

CONCERN-2092 identified that this default creates a protocol-exploitable
channel: any admitted participant — including a hostile or malfunctioning
Observer admitted as a sentinel — can post `Add(ParticipantStatus)` carrying
PXA state changes (`CS.P`, `CS.X`, `CS.A`) and, without any Case Owner
confirmation, force PXA adoption as canonical case state and trigger embargo
teardown. The current answer to "what prevents this?" is "don't deploy with
the default" — a configuration posture, not a protocol guarantee.

The design question is: **what should the default backend be for
security-significant Evaluator call-out gates, and should that default be
implemented as a reusable pattern?**

## Decision Drivers

- A permissive default for gates that control unilateral state change or
  embargo consequences is a protocol-level security risk, not just an
  inconvenience
- The same approval pattern recurs: status adoption, invitation suggestions,
  embargo proposals, and other protocol actions all benefit from a
  Case Owner approval gate
- Existing AS2 `Offer`/`Accept`/`Reject` vocabulary is sufficient for the
  round-trip — no new message types are needed
- The ADR-0025 ceiling/floor rule was designed for simulation-domain fuzzer
  nodes where permissive defaults are a prototype-stage convenience; it does
  not apply where permissiveness creates an exploitable channel
- Reusable tree factory reduces per-gate implementation cost and ensures
  consistent semantics across all approval flows

## Considered Options

1. **Keep `AlwaysSucceed` as default** — permissive; production hardening is
   opt-in configuration. No code change; conservative posture requires explicit
   operator action.
2. **`AlwaysFail` as default** — conservative but semantically wrong: no
   non-owner PXA assertion would ever be adopted, making the gate a permanent
   block rather than a configurable approval seam.
3. **`RequireCaseOwnerApproval` as default** — conservative and correct:
   non-owner assertions require explicit Case Owner confirmation via an
   Offer/Accept/Reject round-trip before adoption. Permissive behavior is an
   explicit operator opt-in.

## Decision Outcome

Chosen option: **`RequireCaseOwnerApproval` as default** (option 3), because
it provides a meaningful conservative default — the Case Owner must explicitly
approve — while using existing AS2 vocabulary, being composable with any
policy, and making permissive behavior a visible, documented operator choice.

`RequireCaseOwnerApproval` is defined as a reusable Evaluator call-out
backend that:

- Sends an `Offer` activity to the Case Owner carrying the pending action as
  the object
- Waits for an `Accept` or `Reject` in reply using existing AS2
  `Accept`/`Reject` vocabulary
- Returns `SUCCESS` on `Accept`, `FAILURE` on `Reject` or timeout

The backend is implemented as a shared tree factory with parameters for the
subject and the CaseActor context, composable into any Evaluator call-out
seam that requires Case Owner approval.

**Capability shape:** Evaluator — the call-out answers a yes/no question
("is this action approved?"). The internal Offer/Accept/Reject mechanics are
an implementation detail of the default backend, not a property of the seam.

> **Amended by ADR-0080 (2026-08-31).** The capability-shape assignment above is
> **incorrect**, and the deny-always stub that satisfied this ADR is the symptom.
> At the moment authorization is first needed no answer exists, so an Evaluator
> asked "is this approved?" can only ever answer *no* — which is exactly what
> `RequireCaseOwnerApprovalNode` does. The round-trip is therefore not an
> implementation detail hidden behind an Evaluator seam; it determines the shape
> of the seam. Each gate is a **conversation-state routing subtree**
> (ASK-02-001, RSH-07-004): it routes on whether authorization has been recorded,
> refused, requested-and-outstanding, or never requested, and in the last case
> emits the request and terminates successfully — `SUCCESS` meaning *I asked*.
>
> The conservative-default requirement this ADR establishes is **unchanged**, and
> so is the project-wide floor rule for security-significant call-out points.
> What changes is that the conservative default is now reachable: before ADR-0080
> the model specified here was unimplementable by any pathway (CONCERN-2812).
> See also RSH-07-005 — a blocked gate must not be unblocked by configuring the
> permissive backend.

**Scope of the conservative-default rule:** This decision establishes a
project-wide exception to ADR-0025's ceiling/floor rule. For any call-out
point whose permissive default enables unilateral state change or embargo
consequences, the DETERMINISTIC default MUST sit at the floor (most
restrictive semantically-correct backend), not the ceiling. ADR-0025 is
amended in-place to reflect this exception.

**Valid alternative backends (all MAY):** `AlwaysSucceed` (trusted
participants, demo deployments), `AlwaysFail` (reject all non-owner
assertions), role-differentiated policy (Vendor treated differently from
Observer), probabilistic approval (stochastic simulation), and any other
`CallOutBackendFactory`-conformant implementation. None requires a framework
change — each is a different factory injected into the same bundle field.

### Consequences

- Good: the conservative posture requires no configuration; permissive
  behavior is an explicit operator choice with documented consequences
- Good: existing AS2 vocabulary is reused; no new wire message types are
  introduced
- Good: the same `RequireCaseOwnerApproval` factory is composable across
  status adoption, invitation suggestions, embargo proposals, and similar
  flows — one pattern, not many bespoke implementations
- Neutral: demo and trusted-participant deployments must explicitly configure
  `AlwaysSucceed` (or equivalent); this is intentional — permissiveness is
  visible in the code rather than inherited from an implicit default
- Neutral: tests that relied on the `AlwaysSucceed` default must be updated
  to either explicitly configure a permissive bundle or exercise the approval
  flow; this is the correct test behavior
- Bad: existing demo scenarios that relied on `AlwaysSucceed` implicitly will
  fail until updated to configure the permissive backend explicitly

## Validation

- `StatusAuthorizationCallOutBundle` fields default to `RequireCaseOwnerApproval`
  (not `AlwaysSucceed`)
- Tests for `add_participant_status_bt` and `add_case_status_bt` that exercise
  the non-owner path must pass a permissive bundle explicitly; tests that
  exercise the conservative path use the default
- Architecture boundary test (`test_core_no_demo_imports.py`) continues to
  pass after the new backend is added

## More Information

- CONCERN-2092: sentinel actors admitted as Observers can force embargo
  teardown via PXA assertions — the source concern
- ADR-0025 (amended): call-out point factory injection and ceiling/floor rule;
  the security-significant gate exception is added in-place
- ADR-0046 (amended): two-gate authorization model; Consequences updated to
  reflect conservative default
- `notes/received-status-authorization.md`: two-gate design and bundle defaults
- `notes/call-out-configuration.md`: three-mode model and ceiling/floor rule

Generated spec requirements: `specs/received-status-handling.yaml`
RSH-07-001 through RSH-07-003.
