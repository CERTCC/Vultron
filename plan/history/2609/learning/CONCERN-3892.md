---
source: CONCERN-3892
timestamp: '2026-09-30T14:04:47.263514+00:00'
title: 'No received path implements EMB-03-001: a replica never enters EM REVISE on
  an inbound embargo revision'
type: learning
---

## Problem

EMB-03-001 requires a participant in EM `ACTIVE` that receives an embargo revision (EV, `Invite(EmbargoEvent)` on a case that already has an active embargo) to move its EM state to `REVISE`. No received path does this. `InviteToEmbargoOnCaseReceivedUseCase` runs `invite_to_embargo_on_case_tree`, whose effect nodes are `CreateAndStoreInviteNode`, `OptionalLookupParticipantNode` and `UpdateParticipantEmbargoPecNode(INVITE)` — it moves the *invitee's* consent to `INVITED` and records the proposal index, and never touches `case.current_status.em`. `grep -rn "EMB-03-001" vultron/ test/` finds no implementation and no marker test.

Consequences:

- A replica's EM stays `ACTIVE` while the proposer's own store is at `REVISE`. The CASE_MANAGER's authoritative record therefore never reflects that a revision is under negotiation when a non-owner proposes one.
- Anything keyed on `EM.REVISE` runs only in the proposer's container. Under the previous consent model that was the lapse cascade (see #3884); under the revised model (ADR-0093) it is EMB-03-002's counter-revision handling, EMB-03-003 / EMB-04-002 / EMB-05-002's "terminate if P/X/A" branches, and `_project_case_to_stub`'s embargo projection.
- When the owner later accepts the revision, replicas observe `Accept(Invite(B))` with `em_before == ACTIVE`; `accept_embargo_invite(OBSERVED)` tolerates this only because it keys activation on `active_embargo != embargo_id` rather than on the EM state. That is a happy accident, not a design.

Surfaced while planning #3884, where it explained why the lapse-on-propose cascade "ran in one store only". Independent of the consent model, so filed separately rather than folded into that decision.

## What needs deciding

Whether the received EV path should drive the replica's EM machine `ACTIVE → REVISE` via `EmbargoLifecycle.propose_embargo(transition_mode=OBSERVED)` (the pattern the received accept/reject paths already use), and whether the CASE_MANAGER's EM transition for a non-owner's revision is recorded as a ledger entry so every replica learns it (PCR-08-003, CLP-07).

## Acceptance criteria

- [ ] AC-1: Decide where the replica-side `ACTIVE → REVISE` transition belongs (received EV tree vs. ledger replay) and record it in the notes or an ADR if it changes the case-communication model.
- [ ] AC-2: A participant at `EM.ACTIVE` receiving `Invite(EmbargoEvent)` for a case with an active embargo moves to `EM.REVISE` and emits EK (EMB-03-001); one already at `REVISE` receiving a counter-revision stays at `REVISE` (EMB-03-002); tests carry `@pytest.mark.spec` for both.
- [ ] AC-3: The P/X/A branches (EMB-03-003) are reachable on the received side and tested.
- [ ] AC-4: `test_manage_embargo_demo.py` or a new scenario exercises `ACTIVE → REVISE → ACTIVE` across two containers so the CASE_MANAGER's and a participant's EM states are both asserted.

## Governing specs

EMB-03-001, EMB-03-002, EMB-03-003, EMB-04-001, EMB-05-001, PCR-08-003, CM-17-002, MSM-07-005. ADR-0093, ADR-0108.

**Resolved**: 2026-09-30 — implementation tracked in #3913 (manager-side relay) and #3915 (participant side and replay nodes). Decision recorded as ADR-0113 (embargo revision negotiation relays through the CASE_MANAGER; the ledger carries state but never asks), planned as a bundle with Concerns #3836 and #3863.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3912>.
Spec: `specs/embargo-policy.yaml` (EP-09, EP-04-011, EP-08-004); `specs/em-behavior.yaml` (EMB-03 description).
Notes: `notes/embargo-lifecycle.md`, `notes/case-communication-model.md`, `notes/participant-embargo-consent.md`.
