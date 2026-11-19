---
source: CONCERN-6641
timestamp: '2026-11-19T14:46:46.349080+00:00'
title: Decide what a case invite preview shows, withholds or leaves out, field by
  field
type: learning
---

Theme: theme:wire-delivery — an invitee's case preview shows what helps them decide whether to join, and a case manager can withhold only the details deliberately chosen as withholdable.

## Summary

#6372 has to say which case preview fields may carry the `Redacted` marker. Neither the specs nor ADR-0193 decide that, and CM-17-010 lists the preview's exact contents (`id`, `type`, `summary`, embargo terms), so as written any marker breaks it. The user asked for this to be decided deliberately in a planning session, not picked inside the build (epic run #6511, 2026-11-18).

## Surface Symptom vs. Underlying Problem

- **Symptom:** #6372 can't finish AC-2, AC-5, AC-6 or AC-7, because no field is open to the marker (`CasePreview.redactable_fields` is empty in PR #6634).
- **Underlying problem:** nothing has decided what an invite preview is for, field by field: what it shows, what may be withheld, and what is left out. The marker question is one part of that.
- **What stays:** the preview is the case's AS2 `preview` typed `CasePreview` (ADR-0205, PR #6616); `summary` stays a shown value (MV-10-001); a marker outside an opened preview field is refused (MV-12-002, PR #6634).

## Category

Design gap (specification).

## Severity

Medium. It blocks the rest of Focus Task #6372.

## Evidence

User direction from the run:
- Be deliberate rather than making a quick pick.
- The case title (`name`) is an odd thing to withhold and should probably be shown.
- The case's details (its description, `content`) are what a sender would expect to hold back in an invite preview.
- Adding more case facts to the preview, such as vul IDs or severity, is in scope.

Also decided in the same run, for the planning to carry into the specs: a leaky marker, one that carries the withheld value, is the **sender's** responsibility, not the receiver's. The receiver applies the normal unknown-key handling (MV-11-003). MV-12-005's receiver-side refusal becomes a sender-side MUST: the preview builder never puts a withheld value in a marker (MV-12-004). #6372's AC-3 changes to match.

## Impact if Ignored

#6372 stays open, a preview can't mark anything withheld, and CM-17-010 contradicts ADR-0193.

## Suggested Action

Plan this with `plan-issue` and an interview. Expected output:
- a field-by-field table for the case preview: show, may withhold, or leave out;
- amendments to CM-17-010 and MV-12 (MV-12-005 moves to the sender);
- an updated AC list on #6372.

This is not #6257, which covers previews of other objects. Related: PR #6634, part 1 of #6372.

Governing specs: CM-17-010, MV-10-001, MV-11-003, MV-12-001, MV-12-002, MV-12-003, MV-12-004, MV-12-005. ADRs: ADR-0193, ADR-0205.


**Resolved**: 2026-11-19 — implementation tracked in #6372, #6692, #6693.
Docs PR: https://github.com/CERTCC/Vultron/pull/6695.
ADR: ADR-0217 (new), ADR-0193 (revision 2).
Notes: `notes/selective-disclosure.md`.
