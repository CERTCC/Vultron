---
source: ISSUE-710
timestamp: '2026-06-11T18:36:22.073410+00:00'
title: 'Embargo received-side BT adoption: lenient/strict nodes, actor-id handoff,
  BT-14-001'
type: learning
---

## 2026-06-09 ISSUE-710 — Embargo received-side BT adoption

- BT node parameter shadowing: When migrating procedural logic to BT nodes,
  ensure constructor parameters are used or removed. The unused `actor_id_source`
  parameter in LookupParticipantNode was defined but never used, creating
  confusion about parameter intent.
- Actor-id mismatch in invite trees: InviteToEmbargoOnCaseReceivedUseCase
  passes wrong actor_id to bridge.execute_with_setup() when invitee_id differs
  from sender actor_id. Must pass invitee_id (not sender) so
  OptionalLookupParticipantNode resolves correct participant record.
- Lenient vs strict node variants: OptionalLookupParticipantNode pattern
  (succeed-on-missing) is correct for operations that should skip when
  participant missing (invite, reject), but LookupParticipantNode
  (fail-on-missing) is still needed for operations that require participant
  (acceptance recording).
- Cascade subtree must be part of tree execution: All BT factories include
  CommitLogCascadeNode as a leaf; cascade is never a post-BT callback.
- Post-implementation code review caught actor_id bug before merge; review
  gates on correctness, not style.
- BT-14-001 compliance is CRITICAL for peer broadcast nodes: CommitLogCascadeNode
  MUST return FAILURE when cascade dispatch fails, not SUCCESS. Masking delivery
  failure with SUCCESS causes silent state divergence (missed by initial code
  review, found on PR review). Always check peer-broadcast nodes against BT-14-001.
- Lenient vs strict patterns need documentation: OptionalLookupParticipantNode
  (lenient) is correct for optional workflows where participant may not exist
  locally yet, but the architectural rationale must be explicit in docstrings
  so future reviewers understand why "Always SUCCESS" is intentional, not a bug.
  The pattern supports broadcasting log entries even when participant doesn't
  exist on this peer yet (state gap resolved by broadcast reception).

**Promoted**: 2026-06-11 — captured in `notes/bt-integration.md` §
"Lenient vs. Strict Participant Lookup Node Variants".
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
