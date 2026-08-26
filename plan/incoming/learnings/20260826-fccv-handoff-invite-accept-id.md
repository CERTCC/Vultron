---
title: "fccv_handoff: find_case_invite_for_actor return value discarded; accept uses original invite.id_"
type: learning
timestamp: "2026-08-26"
source: ISSUE-2203
signal: concern
---

In `vultron/demo/scenario/fccv_handoff_demo.py` lines 287–301, the
`find_case_invite_for_actor` call is wrapped in `demo_check` and its return
value is discarded.  The subsequent `accept-case-invite` trigger uses
`invite.id_` (the original C1-created Invite ID) rather than the
CaseActor-forwarded Invite ID.

This is a partial fix: the mail-carrying is gone (no `post_to_inbox_and_wait`),
but the `accept-case-invite` trigger may reference an ID that the invitee's
DataLayer holds under a different key (the CaseActor-forwarded ID, not the
original).

AC-4 for `fccv_handoff_demo.py` was not listed as a defect in the issue (only
`fccv_extension` and `fcvcv` were called out), but the same pattern applies.
Recommend filing a follow-up Bug/Task to capture the forwarded invite ID from
`find_case_invite_for_actor` and use it in the `accept-case-invite` trigger
body, and to upgrade the `demo_check` to a `demo_gate`.
