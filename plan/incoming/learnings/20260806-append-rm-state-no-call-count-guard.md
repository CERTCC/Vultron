---
title: append_rm_state has no per-session call-count guard; valid-transition chains silently over-advance RM state
type: learning
timestamp: 2026-08-06
source: ISSUE-2017
signal: concern
---

`CaseParticipant.append_rm_state()` validates each individual hop against
`is_valid_rm_transition`. It cannot detect a caller that strings together a
chain of valid individual transitions (e.g. START→RECEIVED, RECEIVED→VALID,
VALID→ACCEPTED) when only one was appropriate for the construction context.

This is the root class of bug fixed in #2017: the node called
`append_rm_state` three times, all individually valid, but the business rule
(CM-11-001) only permits recording RM.RECEIVED at Accept(Invite) time.

**Risk**: Any future BT node that creates a `VultronParticipant` and calls
`append_rm_state` multiple times will silently reproduce this class of bug.

**Suggested fix**: A `VultronParticipant.from_invite(case_id, invitee_id, roles)`
named constructor that calls `append_rm_state(RM.RECEIVED)` exactly once would
encode the CM-11-001 invariant structurally. Tracked as Concern #2042.

**Promoted**: 2026-08-17 — captured in GitHub #2042 (open Concern — already tracked).
Docs PR: TBD.
