---
source: NOTES-case-joining--what-the-old-model-got-wrong
timestamp: '2026-10-08T17:52:41.111096+00:00'
title: 'Archived: notes/case-joining.md - what the old model got wrong'
type: note
---

## Issue #4052 — archived from notes/case-joining.md

Section "What the old model got wrong", archived because the join model (ADR-0114, ADR-0121, ADR-0116) is implemented and the note's Flow and Pitfalls now carry the orientation. Each item below was fixed by the child issue named in it.

## What the old model got wrong

**The participant record came after the reply.** `CaseParticipant` was created
when the CASE_MANAGER processed `Accept(Invite)`. The case therefore held no
record of an invitee that had not answered — or that declined — which is
exactly what the CASE_MANAGER needs to track. The embargo-consent model's
`INVITED` state already assumed a pre-reply record.

**Roster membership was doing the job of the consent check.** `case_addressees`
returned the whole roster, and nearly every case-content send used it. CM-10-004
and VP-08-006 (no case content before embargo acceptance) held only because a
non-accepted actor was not in the roster. Putting invitees in the roster without
the filter would have leaked every ledger entry to them. The filter now lives in
the shared recipient selection, not at each send site, and `case_addressees` is
gone (#4046).

**An invitee validated a report it was never offered.** ADR-0121 originally had
the invitee recover the reporter's `Offer(VulnerabilityReport)` from the ledger
replay and answer it with the standard `validate-report`. Two things are wrong
with that. A reply must answer a message sent to the replier. And the joiner
judges the *case* — for a late joiner, the report plus everything that built up
during coordination — not the original submission, which may have been far
sparser.

**`Accept(Invite)` was read as joining only, while the wire factories labelled
it RV.** CM-11-001 said `Accept(Invite)` leaves RM at `RECEIVED`; the factory
docstrings called it the RV message and `Reject(Invite)` the RI message. Both
were half right: there are two Invites. Accepting the stub is joining (no RM
move); accepting the full-case Invite is RV.

**Status updates created participants.** The original ADR-0084 scoped
on-behalf `v→V` to a vendor "not yet — or never — a participant", so the on-behalf tree minted a
participant for an absent target, saved it, and then — for `d→D` — had the RM↔D
entailment refuse the write, leaving a stray record behind. A status update is
never a way into a case.

**The stub and the case were the same thing on the wire.** Same `type`, same
ID; a stub differed only in which fields it carried, so no message could be
about the stub as distinct from the case. Fixed in #4045: the stub is
`VulnerabilityCaseStub` with ID `<case-id>/stub` and a `caseId` naming the case
(CM-11-013), and it carries only that plus the embargo terms (CM-17-010).

**The RM model could not say "no" from *Received*.** `R → C` did not exist, yet
two paths already closed from other rungs by bypassing the transition table:
`Leave(Case)` through `force_rm_state`, and the report hard-reject. ADR-0114
adds `R → C` only. `V → C` stays out: VP-02-004 forbids closing from *Valid*,
so a `Leave` from `VALID` is recorded as `V → D → C`. Both landed in #4044, which
also retired the closure uses of `force_rm_state` and guarded the hard-reject.
