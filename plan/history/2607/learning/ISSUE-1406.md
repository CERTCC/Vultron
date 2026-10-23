---
title: suggest-actor Accept path does not thread CaseParticipant roles into Invite
type: learning
timestamp: '2026-07-14T00:00:00Z'
source: ISSUE-1406
---

In the `create_accept_actor_recommendation_received_tree` path (CaseActor
receives `Accept(Offer(CaseParticipant))` from Case Owner), the
`suggested_roles` blackboard key is **never written**. `EmitInviteActorToCaseNode`
reads this key via `_read_suggested_roles()`, gets a `KeyError`, and returns
`None` — passing `roles=None` to `factory.invite_actor_to_case()`.

The resulting `Invite` has `roles=None`, so after `Accept(Invite)` the new
`VultronParticipant.case_roles` is `[]`. This is documented behavior, not a
bug (ADR-0032, BT-HELPER-01: no silent default substitution).

Contrast with `create_recommend_actor_to_case_received_tree` (fresh path):
that tree writes `suggested_roles_{id_segment}` (namespaced, per BTND-03-004)
via `EvaluateDefaultRolesNode`, then reads it in `EmitOfferCaseParticipantToOwnerNode`.
The key used by `EmitInviteActorToCaseNode` is the flat `suggested_roles` key,
which the Accept path never populates.

**Takeaway**: When writing tests for the suggest-actor path that verify roles
end up on a participant, check which sub-tree is under test. Only the
`invite_actor_to_case_trigger_bt` path (or a manually-constructed tree with
`EvaluateDefaultRolesNode`) will produce a non-empty `case_roles`. The
`AcceptOfferCaseParticipant` use case always produces `roles=None` in the Invite.

**Promoted**: 2026-07-15 — captured in notes/bt-integration.md.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1458>8>8>8>8>.
