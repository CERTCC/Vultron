---
source: NOTES-case-state-model--cm-03-006-rename
timestamp: '2026-09-17T17:13:54.587136+00:00'
title: 'CM-03-006 Rename: case_status to case_statuses'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** vultron/wire/as2/vocab/objects/vulnerability_case.py:111

---

## CM-03-006 Rename: `case_status` → `case_statuses`

Spec `CM-03-006` requires renaming `VulnerabilityCase.case_status` (a list
field with a misleading singular name) to `case_statuses`. The same rename
applies to `CaseParticipant.participant_status` → `participant_statuses`.

**Before starting the rename**, quantify scope:

```bash
grep -rn "\.case_status" vultron/ test/
grep -rn "\.participant_status" vultron/ test/
```

As of the last review, `handlers.py` alone has approximately 20 call sites.
Total scope across `core/behaviors/` and tests makes this a high-breakage
change.

**Recommended approach**: Do both renames (`case_statuses` and
`participant_statuses`) in a single PR to keep the diff localized and avoid
a partial-rename state that is harder to reason about.

**Cross-reference**: `AGENTS.md` "case_status Field Is a List (Rename
Pending)"; `specs/case-management.yaml` CM-03-006.

---
