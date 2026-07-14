---
title: "BTND-03-004 partial scope: participant_accepted_status and owner_initial_status still flat"
type: learning
timestamp: 2026-07-14
source: ISSUE-1397
---

When namespacing blackboard keys per BTND-03-004, review ALL inter-node handoff keys within
the affected subtree, not just the ones listed in the issue body.

For issue #1397 the named keys (`new_case_participant`, `participant_case`, `new_participant_id`)
were namespaced. Code review caught two more flat keys inside the same subtree:

- `participant_accepted_status` (writer: `ResolveParticipantAcceptedStatusNode`, reader: `CreateParticipantNode`)
- `owner_initial_status` (writer: `ResolveOwnerInitialStatusNode`, reader: `CreateOwnerParticipantNode`)

These were left flat because they are intra-Sequence (currently low-risk), but they violate
BTND-03-004 and will be addressed in follow-up #1418.

**Lesson**: When implementing BTND-03-004 fixes, use grep to find ALL `register_key` calls
within the composite subtree and audit every key for whether it crosses concurrent execution
boundaries, not just the keys explicitly named in the issue.
