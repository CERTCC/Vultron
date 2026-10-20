---
source: CONCERN-4885
timestamp: '2026-10-20T14:56:45.195541+00:00'
title: No direct-message path from the CASE_MANAGER or Case Owner to a participant
  outside the case ledger
type: learning
---

## Summary

The CASE_MANAGER and the Case Owner have no way to send a participant a direct message that stays between them. The only note path is `Add(Note)` to the case: the CASE_MANAGER attaches the note and commits an `add_note_to_case` ledger entry, and that entry fans out to every active participant.

\#4829 moves the CASE_MANAGER's participant-specific notes onto that path: the RSH-06-004 RM-anomaly clarification, the CSB-18 diagnostic, and the CM-16-016 reinforcing-suggestion note to the Case Owner. Each one is addressed to a single actor, but now every active participant sees it in the case. That is fine for these notes today. Still, the protocol cannot express "tell this one participant something without putting it in the case record"

## Gap

- A participant's received `Add(Note)` handler refuses everything not addressed to the CASE_MANAGER (HP-01-005, PCR-08-001). A participant has no receive path for a note meant only for it.
- `Create(Note)`, the ActivityPub-native direct-message form, was retired by #4707 (VAM-01-011). Notes outside any case are an open question (MS-18-001, `docs/topics/future_work/_oq-create-then-add.md`).
- An actor that is not yet active (for example, an invitee whose full-case reply was refused) gets no ledger fan-out (CM-10-004). So it cannot be told why, even through a broadcast note.

## Why it may matter later

Clarification requests, embargo-negotiation side conversations, or remediation guidance may need to be private, or may need to reach an actor the case does not yet entitle to its content. Whether Vultron needs this at all is undecided. This issue records the gap so that a later design decides it on purpose.

## Open questions

- Is a private CASE_MANAGER/Case Owner → participant message a protocol requirement, or something left to out-of-band channels?
- If it is needed, what is its wire form (a `Create(Note)` addressed to one actor, outside the case record?), and does it get a ledger entry?
- Can it reach an inert invitee?

Where: vultron/core/use_cases/received/note.py
Source: #4829

**Resolved**: 2026-10-20 — implementation tracked in #4941.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4944>.

Decision: a private Case Manager → participant note is not a protocol
requirement now. It is recorded as a deferred form on the Open Questions page
that the protocol would allow (MAY) but never require, and that may reach an
inert participant; Idea #4941 tracks the demo that would decide its wire form.
An inert invitee refused by a precondition guard already learns why from the
refusal notice (CLP-05-001).
