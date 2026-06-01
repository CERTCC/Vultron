---
source: Priority 470
timestamp: '2026-06-01T17:56:24.617105+00:00'
title: 'Priority 470: Two-Actor Demo Redesign'
type: priority
---

Completed redesign of the two-actor (Reporter + Vendor) CVD demo implementing a complete,
correct end-to-end CVD workflow: report submission, case creation with Case Actor handoff,
embargo bootstrap, fix lifecycle (VF → VFD → VFDPxa), embargo teardown, and case closure.

Epic: #464

## Completed issues

- #460 — Sub-issue A: Documentation and spec updates
- #461 — Sub-issue B: Core capabilities
- #462 — Sub-issue C: CASE_MANAGER role delegation protocol
- #469 — Case Actor spawning and CASE_MANAGER delegation automation
- #463 — Sub-issue D: Demo replacement
- #475 — Case Actor URN-based ID makes it unreachable via HTTP delivery
- #476 — Remove spec-violating workarounds from SvcAddParticipantStatusUseCase
- #483 — two_actor_demo.py: participant fetch, status check, and exception handling bugs
- #484 — Type narrowing: _resolve_current_participant_state() returns tuple[Any, Any]
- #467 — BT refactor: AddParticipantStatusToParticipant handler
- #489 — Extract shared helpers into vultron/demo/helpers/
- #521 — PCR-07: Integration tests for case-replica bootstrap and late-joiner sequences (parent)
  - #522 — PCR-07-006: bootstrap sequence
  - #523 — PCR-07-007: late-joiner sequence
- #527 — Integration demo suite takes 17+ min in CI — polling helpers not patched
- #530 — Demo integration tests share a single DataLayer across actors
- #534 — Co-located actors in same process share module-level singletons
- #570 — Demo CI: GitHub Actions integration workflow + demo runner hardening
- #589 — SvcAddParticipantStatusUseCase sends RM.START after notify-published
- #593 — Post-case-creation participant messages bypass Case Actor (parent)
  - #594 — Fix outbound routing: participant trigger use cases must address Case Actor only
  - #595 — Implement automatic CaseLogEntry + Announce(CaseLogEntry) broadcast cascade
  - #596 — Refactor sender-side trigger use cases into Behavior Trees
- #466 — Docs: two-actor-demo tutorial + technical reference
- #471 — Tutorial: docs/tutorials/two-actor-demo.md
- #472 — Technical reference: docs/reference/two-actor-demo-protocol.md
