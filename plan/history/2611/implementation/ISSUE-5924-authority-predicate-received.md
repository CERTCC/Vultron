---
source: ISSUE-5924-authority-predicate-received
timestamp: '2026-11-06T04:21:06.640369+00:00'
title: Received-side sender-authority checks take the boolean from has_role
type: implementation
---

PR: https://github.com/CERTCC/Vultron/pull/5994

The last two received-side sites that compared `resolve_case_manager_id(...)`
exactly with the sender id (`_pending_refusal.close_refused_embargo_ask` and
`embargo/invite.resolve_proposer_id`) now ask
`has_role(actor_id, case_id, CVDRole.CASE_MANAGER, dl)` (ARCH-24-008). A roster
that spells the CASE_MANAGER with a trailing slash now counts as the manager at
both sites (OID-01-006); a roster with two CASE_MANAGER holders answers as
before, with the resolver's first holder.

The ARCH-24-009 ratchet reached its terminal value and is inverted: the scan
must report no site, while the module scan, the compliant-asker scan and the
per-shape synthetic controls keep it from passing vacuously. ARCH-24-009's
`verification:` text now describes the inverted assertion.

`test_participants_reject_leaves_the_proposal_pending` passed at the reject
use case's door guards (the participant is not the Invite's invitee) and never
reached the authority check; it now calls `close_refused_embargo_ask` directly,
and fails when the check is removed.
