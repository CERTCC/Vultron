---
source: ISSUE-4081
timestamp: '2026-10-08T00:59:24.095679+00:00'
title: 'EmitAddCaseParticipantNode pattern for Add(CaseParticipant) (superseded by
  #4081)'
type: note
---

Archived from `notes/case-ledger-authority.md` by #4081: the CASE_MANAGER no
longer emits `Add(CaseParticipant)` after a stub-Invite acceptance, and
`EmitAddCaseParticipantNode` is deleted (CM-31-012, ADR-0116). Replicas seat a
new member from the `Accept(Invite)` entry; recipients come from
`vultron/core/participants/recipients.py` (CM-10-007).

## `EmitAddCaseParticipantNode` Pattern for `Add(CaseParticipant)` (Issue #1689)

After `PersistInviteeParticipantNode` records the new participant in the
DataLayer, `EmitAddCaseParticipantNode` (in
`vultron/core/behaviors/case/nodes/accept_invite.py`) fans out
`Add(CaseParticipant, Case)` to all existing participants and commits a
canonical `CaseLedgerEntry`.

**Fan-out delivery**: recipients are resolved from
`case.actor_participant_index.keys()` (HTTP actor URLs), **not** from
`case.case_participants` (which stores bare UUID participant IDs as strings
in the DataLayer). Using bare UUIDs as inbox delivery targets causes
`"Request URL is missing 'http://'"` errors. The actor-participant index
keys are always proper HTTP URIs.
