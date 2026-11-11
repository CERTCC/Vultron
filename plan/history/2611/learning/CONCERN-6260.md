---
source: CONCERN-6260
timestamp: '2026-11-11T17:05:33.637272+00:00'
title: Create(CaseParticipant) sets a target that AS2's Create does not take
type: learning
---

Theme: theme:wire-delivery — `Create(CaseParticipant)` carries only the fields AS2's Create defines, so an AS2 reader does not take it as an Add.

## Summary

`Create(CaseParticipant)` sets `target` = the case. AS2's `Create` takes no `target`; seating a participant in a case is the separate `Add(CaseParticipant, target=<case>)`.

## Surface Symptom vs. Underlying Problem

- **Symptom:** an extra `target` on one Create; no other `Create` sets one.
- **Underlying problem:** AS2 Core App. B maps the AS1 "post" verb to Create without a target and to Add with one, so a `Create` with a `target` reads as "added to" and blurs creation with seating. Creating the record and seating it as two acts is correct and should stay.

## Category

AS2 conformance.

## Severity

Low.

## Evidence

Verified on `origin/main`: `vultron/wire/as2/factories/case_participant.py` (~line 83) `_CreateParticipantActivity(object_=participant, target=case_target_ref(target), ...)`.

## Impact if Ignored

Another AS2 implementation may treat the Create as membership; the one-meaning rule for `target` ("where something goes") has an exception.

## Suggested Action

Drop `target` from `Create(CaseParticipant)`; carry the case in `context` (the existing rule for case activities); check the received pattern and any reader of the Create's target.

## References

- `notes/activitystreams-semantics.md` § "Choosing AS2 Terms" and `notes/as2-vocabulary-alignment.md` (docs PR on branch `docs/as2-vocabulary-alignment`).

**Resolved**: 2026-11-11 — implementation tracked in #6295; follow-up Idea #6293
(the Case Owner's removal and reinstatement requests name the Actor). The form stays
`Create`, because `Add(CaseParticipant, target=<case>)` is already the Case Owner's
reinstatement request (CM-31-011).

Docs PR: https://github.com/CERTCC/Vultron/pull/6294.
Notes: `notes/as2-vocabulary-alignment.md`, `notes/activitystreams-semantics.md`.
