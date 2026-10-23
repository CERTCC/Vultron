---
title: "INLINE-OBJ-C \u2014 Prohibit object_=None on semantic-dispatch classes"
type: implementation
timestamp: '2026-04-17T00:00:00+00:00'
source: INLINE-OBJ-C
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6505
legacy_heading: "Phase INLINE-OBJ-C \u2014 Prohibit object_=None on semantic-dispatch\
  \ classes (COMPLETE 2026-04-17)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-17'
---

## INLINE-OBJ-C — Prohibit object_=None on semantic-dispatch classes

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6505`
**Canonical date**: 2026-04-17 (git blame)
**Legacy heading**

```text
Phase INLINE-OBJ-C — Prohibit object_=None on semantic-dispatch classes (COMPLETE 2026-04-17)
```

**Legacy heading dates**: 2026-04-17

Removed `| None` and `default=None` from `object_` fields on all 37 activity
classes in `vultron/wire/as2/vocab/activities/` where the `ActivityPattern`
inspects `object_.type` for semantic dispatch. An omitted or `None` `object_`
always caused `ActivityPattern._match_field` to return `False`, routing the
activity to `UNKNOWN`. Making `object_` required at construction time prevents
this class of silent dispatch failure.

### Files changed

- `vultron/wire/as2/vocab/activities/report.py` — 6 classes
- `vultron/wire/as2/vocab/activities/case.py` — 14 classes (not `RmInviteToCaseActivity`)
- `vultron/wire/as2/vocab/activities/actor.py` — 3 classes
- `vultron/wire/as2/vocab/activities/embargo.py` — 7 classes
- `vultron/wire/as2/vocab/activities/case_participant.py` — 5 classes;
  removed redundant `if self.object_ is not None:` guard in `set_name` validator
- `vultron/wire/as2/vocab/activities/sync.py` — 2 classes
- `vultron/core/use_cases/triggers/embargo.py` — replaced the
  `dehydrated_embargo_id`/strip-then-validate pattern with a data-layer
  resolution of `EmbargoEvent` before calling `model_validate`, so the coerced
  `EmProposeEmbargoActivity` always has a valid `object_: EmbargoEvent`
- `specs/message-validation.yaml` — added `MV-09-003` requirement and
  verification criteria
- `test/wire/as2/vocab/test_actvitities/test_inline_object_required.py` —
  expanded imports; added `TestNoneObjectRejected` with 74 tests (37 classes ×
  `object_=None` + missing `object_`)

### Test results at completion

1607 passed, 12 skipped, 182 deselected, 5581 subtests; `black`, `flake8`,
`mypy`, `pyright` all clean.
