---
source: NOTES-case-communication-model--delegated-flows-exhaustive
timestamp: '2026-10-12T19:38:23.753964+00:00'
title: Delegated Flows (Exhaustive)
type: note
---

**Archived:** 2026-10-12
**Reason:** inventory of delegated-emit callsites; the helper-use ratchet test enforces it
**Superseded by:** test/architecture/test_delegated_attribution_uses_helper.py; CM-24-005

---

## Delegated Flows (Exhaustive)

| Trigger use case | Notes |
|---|---|
| `SvcInviteActorToCaseUseCase` | ✅ emits nothing delegated since #3821: it sends the owner's own Offer, and the delegated emit is the CASE_MANAGER's owner-direct branch of `create_recommend_actor_to_case_received_tree`, a received-side emit under `create_case_manager_gated_tree` (CM-17-007) |
| `SvcOfferCaseOwnershipTransferUseCase` | ✅ fixed in #2173 |
| `invite_to_embargo_on_case_tree` — CASE_MANAGER arm (EP-09-002) | ✅ built in #3913 (ADR-0113) — a *received*-side delegated emit, as CM-24-004 allows: `RelayEmbargoInviteToEachNode` relays `Invite(EmbargoEvent)` to every participant except the proposer with `actor=CASE_MANAGER`, `attributed_to=proposer`, each emission committed in the emitting tree; the proposer comes from `resolve_proposer_id()` (the Invite's `actor`, or its `attributedTo` when the proposal was itself relayed) |
| Other trigger use cases | audit complete — no other delegated-emit callsites |
