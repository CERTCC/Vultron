# AGENTS.md — `vultron/core/behaviors/case/nodes/suggest_actor/`

Agent guidance for suggest-actor BT nodes in this package.

> For project-wide BT conventions see
> [`vultron/core/behaviors/AGENTS.md`](../../../AGENTS.md).

---

## suggest-actor Accept Path Does Not Thread Roles Into Invite

(ISSUE-1406, 2026-07-14)

`create_accept_actor_recommendation_received_tree` (CaseActor receives
`Accept(Offer(CaseParticipant))` from Case Owner) never writes the
`suggested_roles` blackboard key. `EmitInviteActorToCaseNode` reads this key
via `_read_suggested_roles()`, gets a `KeyError`, and passes `roles=None` to
`factory.invite_actor_to_case()`. The resulting `Invite` carries `roles=None`,
so after `Accept(Invite)` the new `VultronParticipant.case_roles` is `[]`.

This is documented behavior (ADR-0032, BT-HELPER-01: no silent default
substitution), not a bug.

**Test implication**: Only the `invite_actor_to_case_trigger_bt` path (or a
tree with `EvaluateDefaultRolesNode`) produces a non-empty `case_roles`. The
`AcceptOfferCaseParticipant` received-side use case always produces
`roles=None` in the Invite. Tests that verify roles end up on a participant
MUST exercise the trigger path, not the received path.

**Blackboard key contrast**:

| Tree factory | Key written | Namespaced? |
|---|---|---|
| `create_recommend_actor_to_case_received_tree` | `suggested_roles_{id_segment}` | ✅ |
| `create_accept_actor_recommendation_received_tree` | *(never written)* | N/A |
