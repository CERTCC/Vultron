---
source: ISSUE-1397
timestamp: '2026-07-14T18:21:02.285566+00:00'
title: namespace participant blackboard keys by report_id
type: implementation
---

## Issue #1397 — fix: namespace new_case_participant / participant_case / new_participant_id blackboard keys by report_id

Namespaced three flat inter-node handoff blackboard keys in the participant creation subtrees to prevent concurrent `create_receive_report_case_tree` executions from corrupting each other's in-flight data (BTND-03-004).

Keys: `new_case_participant_{seg}`, `participant_case_{seg}`, `new_participant_id_{seg}` where `seg = report_id.split("/")[-1]`.

Files: `participant_add.py`, `owner.py`, `participant_tree.py`, `create_tree.py` (7 leaf nodes + 2 composites updated), new concurrent-execution regression test added.

PR #1419. Follow-up #1418 tracks two remaining flat keys (`participant_accepted_status`, `owner_initial_status`).
