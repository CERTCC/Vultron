---
status: accepted-provisional
date: 2026-11-18
created: 2026-11-18
updated: 2026-11-18
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0046, ADR-0166 (the records this one consolidates);
  ADR-0076, ADR-0080, ADR-0108; specs/received-status-handling.yaml RSH-01,
  RSH-04, RSH-07; specs/cs-behavior.yaml CSB-18; issues #5465, CONCERN-3008
informed: []
supersedes:
  - 0046-received-status-authorization.md
  - 0166-adopting-p-x-or-a-and-ending-the-embargo-are-one-authorized-step.md
stakeholder_type: [project-contributor]
---

# How the Case Manager Accepts a Reported P, X or A Value

## Context and Problem Statement

A participant reports its view of the case by embedding a suggested `CaseStatus` in its own `Add(ParticipantStatus)`.
When the suggestion sets P (the vulnerability is public), X (an exploit is public) or A (attacks are observed), the CASE_MANAGER must decide whether the value becomes canonical case state, and an adopted value ends the active embargo.
An outside sentinel that is not the Case Owner may be the reporter, so the decision needs a seam of its own.

ADR-0046 gave adoption and teardown a gate each, in two trees joined by a self-addressed `Add(CaseStatus)`.
ADR-0080 then made both gates ask the Case Owner instead of answering inline, and ADR-0108 replaced the loopback with a direct canonical write in one tree.
ADR-0166 removed the teardown gate, because a teardown refused after an adoption leaves P, X or A set beside an active embargo, the state the cross-machine invariants forbid (#5465).
ADR-0046 carried two of those changes as inline amendments, and its chosen option, two gates, no longer held.

This record states the two decisions as one.
It decides nothing they did not.

How does the CASE_MANAGER decide whether a reported P, X or A value becomes canonical, and what follows from adopting it?

## Decision Drivers

- **A hostile or defective participant must not end an embargo without the Case Owner's confirmation** (ADR-0076).
- **The Case Owner's own report is authoritative.** Asking the Case Owner to confirm what it reported, or what it already authorized, is circular.
- **The protocol requirements must not contradict each other.** A participant's composite state never has P, X or A set while an embargo is active, because the P, X or A event is what ends the embargo (CSB-18).
- **P, X and A are facts about the world.** Once the case accepts one, the secrecy the embargo protects is gone or no longer protects users.
- **Canonical state is written before its side effects**, so the termination can name the adopted signals as its cause.
- **An authorization that waits for a human is an ask, not a suspended behavior** (ADR-0080).

## Considered Options

1. **One gate at adoption; adoption and teardown are one CASE_MANAGER act.**
2. **Two gates: one for adoption, one for teardown.** This was ADR-0046's choice, as first built.
3. **Keep the second gate, and make the invariants hold only for a case whose teardown is authorized.**
4. **Keep the teardown seam as a hook that never refuses.**
5. **No gate: always adopt and always tear down.**

## Decision Outcome

Chosen option: **"One gate at adoption"**, because the teardown gate has no authorization question of its own: the adoption gate already stops an untrusted participant from ending an embargo, and a teardown refused after adoption breaks the invariants by design.

### Decision details

1. **The participant's claim is recorded first, then the gate decides adoption.**
   The status adoption gate sits after the node that records the participant's claim and before any canonicalization (RSH-01-001).
   The recorded claim is the legitimate not-yet state that an ask leaves behind, so the tree needs no intermediate state to wait for an answer.

2. **The gate bypasses the Case Owner's report and asks about anyone else's.**
   The gate is a Fallback: a structural check that the sender is the Case Owner, then the Case Owner's approval (RSH-01-002).
   The bypass is tree structure, not a policy that could be misconfigured; the Case Owner is never asked to approve its own report (RSH-07-006).
   A non-owner's P, X or A value is adopted only with the Case Owner's authorization, by default (RSH-07-001, ADR-0076).
   A gate awaiting that authorization is a conversation-state routing subtree: it sends an ask and ends successfully, never answering the question inline (RSH-07-004, ADR-0080).
   A permissive backend may be configured where every admitted participant is trusted, only explicitly and documented, and never to make a blocked path proceed (RSH-07-003, RSH-07-005, RSH-07-007).

3. **One authorization, one act.**
   The authorization of the adoption, or the Case Owner's own report, is also the authorization of the teardown the value calls for; no second approval is asked.
   The CASE_MANAGER act that adopts the value also ends the embargo.
   A future policy that wants to delay a teardown decides at adoption, by not adopting yet.

4. **The adoption is written before the teardown, in the same tree.**
   On adoption the CASE_MANAGER records the post-adoption `CaseStatus` in the canonical ledger, setting each of P, X and A that the case or the adopted status sets and clearing none (RSH-01-003, RSH-01-005).
   It writes it directly, never through a self-addressed `Add(CaseStatus)` or another tree (RSH-04-010, RSH-04-011).
   The teardown and every other canonical-state side effect run after that write (RSH-01-004).

5. **The invariants are judged at act boundaries.**
   They hold for the state each committed CASE_MANAGER act leaves.
   Inside the act, the adoption's snapshot may carry the value beside the still-active embargo, and the invariants do not forbid it.
   The post-act invariant check stays as a safety net for a teardown that fails for another reason (CONCERN-3008).

6. **Only the CASE_MANAGER states the case's status.**
   Every change the CASE_MANAGER makes to EM or PXA state is followed at once by a canonical ledger entry carrying the new `CaseStatus`, announced to the replicas (RSH-04-002 to RSH-04-004).
   An actor that is not the CASE_MANAGER does not emit `Add(CaseStatus)`; it suggests a status inside its own `Add(ParticipantStatus)` (RSH-04-001, RSH-04-007).
   The CASE_MANAGER does not adjudicate its own `CaseStatus` as a received message (RSH-04-008), and a receiver refuses an `Add(CaseStatus)` that the case's CASE_MANAGER did not send (RSH-04-005).

### Consequences

- Good, because the protocol requirements agree, and the invariant is not violated by design.
- Good, because the Case Owner is asked at most once about a P, X or A value, and never about its own report.
- Good, because the conservative default holds: out of the box, a non-owner cannot make the case public or end its embargo.
- Good, because one call-out, not two, has to be configured, backed and fuzzed.
- Bad, because a reader who inspects ledger entries one at a time, inside an act, sees the adoption snapshot beside an active embargo; the invariant tells them to judge at the act boundary.

## Validation

- `test/core/behaviors/status/test_add_participant_status_bt.py` covers the Case Owner bypass, the gate for a non-owner, and an adopted P, X or A value ending the embargo in the same act.
- `test/core/behaviors/status/test_status_authorization_bundle.py` covers the gate's default and the permissive backend.
- `test/architecture/test_teardown_branch_sites.py` pins where the teardown may run.

## Pros and Cons of the Options

### One gate at adoption

- Good, because each authorization question is asked once, by the gate that owns it.
- Neutral, because a policy that wants to delay a teardown must express it as not adopting yet.

### Two gates

- Good, because adoption and teardown each have a named seam.
- Bad, because a teardown refused after an adoption leaves P, X or A beside an active embargo, which the invariants forbid; the deny-by-default teardown gate produced it on every adopted report, the Case Owner's own included.
- Bad, because its reason, that the gates ran in different trees, went away when the adoption and the teardown moved into one tree.

### Make the invariants conditional on an authorized teardown

- Good, because both seams stay.
- Bad, because it makes a causal contradiction a supported state: every participant reading the case is told to keep a secret the case records as public.

### A teardown hook that never refuses

- Good, because the seam stays available for policy.
- Bad, because a seam that must never refuse invites a later backend that refuses, and brings the contradiction back.

### No gate

- Good, because it is the simplest.
- Bad, because any participant could make the case public and end its embargo, with no hook for the Case Owner's judgement.

## More Information

This record supersedes, whole:

- [ADR-0046](archived/0046-received-status-authorization.md): the adoption gate, its Case Owner bypass and the default approval are detail 2; the write-before-side-effect order is detail 4; the outbound emit invariant and the emission authority are detail 6.
  Its two-gate split, the teardown gate and the self-addressed `Add(CaseStatus)` had been replaced.
- [ADR-0166](archived/0166-adopting-p-x-or-a-and-ending-the-embargo-are-one-authorized-step.md): one authorization and one act are detail 3, and judging at act boundaries is detail 5.

Related:

- [ADR-0025](0025-call-out-point-abstraction-layer.md) defines the call-out points the gate uses.
- [ADR-0076](0076-security-significant-gates-default-require-case-owner-approval.md) makes the gate require the Case Owner's approval by default.
- [ADR-0080](0080-protocol-asks-not-suspended-behaviors.md) makes a gate awaiting a human an ask.
- [ADR-0108](0108-one-move-one-mover-case-state-flows-through-the-case-manager-and-the-ledger.md) makes case state flow through the CASE_MANAGER and the ledger, which removed the loopback.

Generated spec requirements: `received-status-handling.yaml` RSH-01, RSH-04 and RSH-07; `cs-behavior.yaml` CSB-18.
