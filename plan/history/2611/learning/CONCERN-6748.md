---
source: CONCERN-6748
timestamp: '2026-11-20T15:36:13.637477+00:00'
title: Participants need a way to share their local tracking IDs with a case
type: learning
---

## Summary

<!-- One or two sentences describing the concern. -->


A participant in a case might have a local tracking number for example a bug tracker ID or other case ID that they use locally for their own tracking system that they need to be able to relate back to this case and so a participant record on a case should be able to contain that, and I believe that means that it probably needs to be part of the participant status record so that it's a self reported claim they can make that we track this case as id foo within our system

## Surface Symptom vs. Underlying Problem

<!--
State two things: (1) the naive, symptom-level reading someone would stop at,
and (2) the deeper problem underneath it that this concern is really about.
Naming both turns the concern into a worked example of the judgment involved —
it shows the jump from the obvious reading to the real one, which is exactly
what makes concerns useful to learn from later.

If the deeper problem also implies parts of the current design that are
*already correct and should not be touched*, say so — knowing what to leave
alone is as valuable as knowing what to change.

Omit only if there genuinely is no gap between the surface reading and the
underlying problem.
-->

The underlying problem is that Vultron cases are coordinating across multiple independent organizations, each of whom presumably already has their own internal tracking systems and so we need a way to directly declare and relate Vultron cases into internal tracking systems so that individual organizations can be sure that they can cross reference from their own tracking cases internally to the Vultron ID it may in fact, be necessary for a participant to be able to have multiple such IDs that should be part of the design is to determine whether that's the case or not and therefore this might be a list of items not just a individual ID within the participant status record

## Category

<!-- Check the one that best fits. -->

- [ ] Top risk
- [ ] Technical debt
- [ ] Security
- [ ] Performance / scaling
- [ ] Fragile / high-churn area
- [x] Other

## Severity

<!-- high / medium / low -->

Low

## Evidence

<!-- Files, modules, or lines where this concern is visible. -->

- `<!-- path/to/file.py -->`

## Impact if Ignored

<!-- What breaks, degrades, or becomes harder if this is not addressed? -->

Without this, it might be harder for individual participants to relate their tracking system to a Vultron case

## Suggested Action

<!-- Recommended fix, mitigation, or next investigation step. -->

Add a field to participant status that can track and contain their tracking IDs as a list or set within a participant status 

Relevant to the removal of participant case name in #6415

---

**Resolved**: 2026-11-20 — implementation tracked in #6762. Docs PR: https://github.com/CERTCC/Vultron/pull/6767. Spec: `specs/case-management.yaml` CM-35.

`ParticipantStatus.tracking_id` already existed as one optional string, but nothing set it and `CreateParticipantStatusNode` dropped it on the next status. The plan replaces it with a set of `{value, tracker?}` entries keyed on `value`. A status that leaves the list out keeps the previous set, a list replaces it, and `[]` clears it. The whole case sees the set, and its entry type is kept apart from a vulnerability's `ids`. The side finding that `case_engagement` has the same gap is tracked in #6763.
