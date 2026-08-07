---
source: ISSUE-2017
timestamp: '2026-08-06T17:51:33.036987+00:00'
title: 'Fix invitee RM entry point: RM.RECEIVED only on Accept(Invite)'
type: implementation
---

## Issue #2017 — Fix CreateInviteeParticipantAtReceivedNode: record RM.RECEIVED only on Accept(Invite)

Per CM-11-001 (corrected by #1756 / PR #2014), `Accept(Invite)` signals willingness to join the case, not triage of the vulnerability report. The prior code recorded R→V→A atomically, conflating case-joining with report triage.

Changes:

- Renamed `CreateInviteeParticipantAtAcceptedNode` → `CreateInviteeParticipantAtReceivedNode`
- Removed `append_rm_state(RM.VALID)` and `append_rm_state(RM.ACCEPTED)` calls; kept only `append_rm_state(RM.RECEIVED)`
- Updated docstrings, comments, and log messages to reference CM-11-001
- Fixed redundant ternary `case_roles=roles if roles else []` → `case_roles=roles`
- Updated tests: renamed methods, assert RM.RECEIVED, exclusion checks for VALID/ACCEPTED

PR: <https://github.com/CERTCC/Vultron/pull/2041>
