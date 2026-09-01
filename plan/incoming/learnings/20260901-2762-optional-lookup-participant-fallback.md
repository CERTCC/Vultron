---
title: OptionalLookupParticipantNode's fallback to the BT actor hides a dropped argument
type: learning
timestamp: 2026-09-01
source: ISSUE-2762
signal: concern
---

`OptionalLookupParticipantNode` (`vultron/core/behaviors/embargo/nodes/conditions.py`
~222) resolves its lookup target as
`self.target_actor_id if self.target_actor_id else self.actor_id`. The fallback
to the BT execution actor is documented as the lenient design, but it makes two
very different situations indistinguishable:

1. "No subject was named, use whoever's replica this is" — intended.
2. "A subject *was* named upstream and got dropped on the way here" — a bug.

Case 2 is exactly what #2762's sibling defect was:
`reject_invite_to_embargo_tree` took a `rejecting_actor_id`, passed it to a
`logger.info` call, and constructed
`OptionalLookupParticipantNode(case_id=case_id)` with no target. The node then
declined the *receiving* actor's consent — the CaseActor's own — and returned
SUCCESS. Nothing in the tree, the logs, or the tests noticed.

Fixed the caller in the #2762 PR. The node's fallback is unchanged, so the same
trap is still available to the next tree that forgets to thread its subject
through. Options if this is worth closing structurally:

- Make `target_actor_id` required and have callers pass the BT actor explicitly
  when that is genuinely what they mean. Two construction sites today
  (`announce_teardown_tree.py` ~207 and ~295), both of which now pass one.
- Or keep the fallback but log at WARNING when it fires, so an accidental
  fall-through is visible in actor output.

Related: the `cc:`-on-invite removal filed as Concern #2996 came out of the same
investigation.
