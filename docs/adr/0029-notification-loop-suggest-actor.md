---
status: accepted
date: 2026-07-22
deciders: [adh]
---

# Notification Loop Collapse: InjectParticipant → suggest-actor-to-case Protocol

## Context and Problem Statement

The simulator `MaybeReportToOthers` BT models the notification loop with
`InjectParticipant`/`InjectVendor`/`InjectCoordinator`/`InjectOther` nodes
that write participant records directly to the case management system. In the
production architecture, participant invitation is handled by the
`suggest-actor-to-case` protocol (Offer → Invite → Accept → Record cascade).
The `InjectParticipant` family bypasses this protocol entirely.

How should the notification loop interact with the production invitation protocol?

## Decision Drivers

- The `InjectParticipant` family must not bypass the `suggest-actor-to-case`
  invite/accept handshake that the production protocol requires
- The outer loop structure ("should we notify additional parties?") represents
  real CVD process logic and should survive
- Party identification Retrievers and effort-gate Evaluators are valid call-out
  points and should survive unchanged
- Vendor/Coordinator/Other role distinction must be preserved when calling
  `suggest-actor-to-case`

## Considered Options

1. Outer loop survives; `InjectParticipant` family replaced by `suggest-actor-to-case`
   trigger with explicit role parameter
2. Entire `MaybeReportToOthers` BT replaced by a standalone orchestrator that
   calls `suggest-actor-to-case` externally
3. Keep `InjectParticipant` family (no collapse; defer to later)

## Decision Outcome

Chosen option: **Option 1** — the outer loop structure survives. The
`InjectParticipant`/`InjectVendor`/`InjectCoordinator`/`InjectOther` Actuator
nodes are replaced by calls to the `suggest-actor-to-case` trigger (or
equivalently, emitting `Offer(Actor)` to the CaseActor). The full
`RecommendActor → Invite → Accept → Record` cascade follows automatically.

### Consequences

- Good, because the `InjectParticipant` family no longer bypasses the protocol
  handshake — participant records are now created only after proper invite/accept
- Good, because party identification, effort gating, and typed sub-loops survive
  unchanged — minimal structural change to the outer BT
- Good, because `suggest-actor-to-case` was generalized for role in #1298
  (now closed); the `_WriteRolesNode` writes the correct `CVDRole` to the
  blackboard before each sub-loop's trigger fires

## More Information

- Planning issue: #1200 (closed); implementation issue: #1311 (closed by PR #1599)
- Simulator nodes: full `MaybeReportToOthers` subtree (see
  `notes/bt-fuzzer-nodes-report-management.md` § "Reporting to Other Parties"
  and "Production Collapse 3")
- Resolved blockers: #1200 (planning) and #1298 (suggest_actor_tree redesign —
  CaseActor-routed suggestion, role parameter), both closed
- Related: ADR-0026 (CaseActor-routed actor suggestion), #1252 (target
  factory function)
- Note: `SetRcptQrmR` RM-state write is handled by the `AcceptInviteToCase`
  cascade; no standalone Actuator is needed at the outer loop layer

Generated spec requirements: `behavior-tree-integration.yaml` BT-20-003
