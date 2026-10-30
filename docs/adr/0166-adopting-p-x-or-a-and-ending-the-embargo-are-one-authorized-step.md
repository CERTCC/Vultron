---
status: accepted-provisional
date: 2026-10-29
created: 2026-10-29
updated: 2026-10-29
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0046, ADR-0076, ADR-0080, ADR-0108; issues #5465, #2885;
  specs/received-status-handling.yaml RSH-01, RSH-02, RSH-07;
  specs/cs-behavior.yaml CSB-04, CSB-05, CSB-06, CSB-18
informed: []
partially_supersedes: 0046-received-status-authorization.md
stakeholder_type: [project-contributor]
---

# Adopting P, X or A and Ending the Embargo Are One Authorized Step

## Context and Problem Statement

When the CASE_MANAGER receives a participant's report that the vulnerability is public (P), that an exploit is public (X) or that attacks are observed (A), it makes two decisions.
ADR-0046 gave each decision its own gate.
The adoption gate decides whether the reported value becomes canonical case state.
The teardown gate then decides whether the embargo that the adopted value calls for may end.
ADR-0076 made both gates require the Case Owner's approval by default.

The cross-machine invariants say that a participant's composite state never has P, X or A set while an embargo is active, because the P, X or A event is what ends the embargo.
A teardown gate that withholds its approval after an adoption leaves exactly that state as the case's settled state.
The two sets of protocol requirements contradict each other, and the deny-always default of the teardown gate produces the contradiction on every adopted report, the Case Owner's own included (#5465).

Which rule gives way: the invariant, or the separate teardown authorization?

## Decision Drivers

- The protocol requirements must not contradict each other.
- A hostile or defective participant must not be able to end an embargo without the Case Owner's confirmation (ADR-0076).
- A gate must have a question of its own to answer.
  Asking the Case Owner to confirm a value it already authorized, or reported itself, is circular, for the same reason ADR-0046 gives the Case Owner's report a bypass at adoption.
- P, X and A are facts about the world.
  Once the case accepts one as true, the secrecy the embargo protects is gone or no longer protects users.

## Considered Options

1. **The invariant wins.** The adoption decision is the one authorization.
   Adopting a P, X or A value and ending the embargo it calls for happen in one CASE_MANAGER act, and the teardown gate is removed.
2. **The authorization wins.** The invariants are restated to hold only for a case whose teardown is authorized.
   The window between adoption and an authorized teardown becomes a named, recorded state, and the receive rules for CP, CX and CA name the authorization step.
3. **Keep the teardown hook, never refusing.** The teardown seam stays as a policy hook with an always-allow default and a name that no longer reads as an authorization.
   A refusing backend would bring the contradiction back, so one must be forbidden.

## Decision Outcome

Chosen option: "The invariant wins", because the teardown gate has no authorization question of its own.
Its purpose under ADR-0076 is to stop an untrusted participant from ending an embargo, and the adoption gate already does that.
Option 2 makes a causal contradiction a supported case state, so every participant that reads the case is told to keep a secret that the case itself records as public.
Option 3 keeps a seam that must never refuse, which invites a later backend that refuses and returns the contradiction.

ADR-0046 weighed a single seam and chose two because the gates then ran in different trees, joined by a self-addressed `Add(CaseStatus)`.
ADR-0108 put both gates in one tree, so that reason no longer holds.
ADR-0046 accepted the invariant violation that a blocked teardown leaves and only detected it, with `PxaEmInvariantDiagnosticNode` (CONCERN-3008); preventing the violation was not weighed.

The decision has three parts:

- **One authorization.** The Case Owner's authorization of a non-owner's P, X or A value, or the Case Owner's own report of it, is also the authorization of the teardown the value calls for.
  No second approval is asked.
- **One act.** The CASE_MANAGER act that adopts the value also ends the embargo.
- **Judged at act boundaries.** The invariants hold for the state each committed CASE_MANAGER act leaves.
  Inside the act, the adoption's case status snapshot is still written before the teardown (RSH-01-004).
  This record keeps that order so the termination can name the adopted signals as its cause.
  That snapshot may carry the value beside an active embargo, and the invariants do not forbid it.

The conservative default of ADR-0076 is unchanged for the adoption gate.
The post-act invariant check stays as a safety net for a teardown that fails for another reason.

### Consequences

- Good: the protocol requirements agree, and the invariant is never violated by design.
- Good: the Case Owner is asked at most once about a P, X or A value, and never about its own report.
- Good: one fewer call-out field, backend set and fuzzer variant to maintain.
- Neutral: a future policy that wants to delay a teardown must decide at adoption, by not adopting yet.
- Bad: a reader who inspects ledger entries one at a time, inside an act, sees the adoption snapshot beside an active embargo. The invariant tells them to judge at the act boundary.

## Validation

- With the default bundle, an adopted P, X or A value ends an active embargo in the same act.
- The received tree has no teardown authorization call-out between the adoption snapshot and the teardown.
- After the act commits, the invariant check finds no violation in the authorized path.

## More Information

This record partially supersedes ADR-0046: its two-gate decision is replaced by one gate.
ADR-0046's adoption gate, its Case Owner bypass, and its write-before-side-effect ordering stand.
