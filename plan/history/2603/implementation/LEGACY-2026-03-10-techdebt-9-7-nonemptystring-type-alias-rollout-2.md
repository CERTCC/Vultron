---
title: "TECHDEBT-9/7 \u2014 NonEmptyString type alias rollout (2026-03-10)"
type: implementation
timestamp: '2026-03-10T00:00:00+00:00'
source: LEGACY-2026-03-10-techdebt-9-7-nonemptystring-type-alias-rollout-2
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 823
legacy_heading: "TECHDEBT-9/7 \u2014 NonEmptyString type alias rollout (2026-03-10)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-10'
---

## TECHDEBT-9/7 — NonEmptyString type alias rollout (2026-03-10)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:823`
**Canonical date**: 2026-03-10 (git blame)
**Legacy heading**

```text
TECHDEBT-9/7 — NonEmptyString type alias rollout (2026-03-10)
```

**Legacy heading dates**: 2026-03-10

`NonEmptyString` and `OptionalNonEmptyString` were already defined in
`vultron/wire/as2/vocab/base/types.py` and partially applied. This task
completed the rollout across all remaining `Optional[str]` fields in
`vultron/wire/as2/vocab/objects/`:

- **`case_event.py`**: Replaced per-field `@field_validator` on `object_id`
  and `event_type` with `NonEmptyString` type annotations; removed validators.
- **`case_reference.py`**: Replaced per-field validators for `url` and `name`
  with `NonEmptyString` and `OptionalNonEmptyString`; removed validators.
- **`vulnerability_record.py`**: Changed `url: str | None` to
  `OptionalNonEmptyString`.
- **`case_participant.py`**: Changed `name` and `participant_case_name` from
  `str | None` to `OptionalNonEmptyString`.
- **`case_status.py`**: Changed `CaseStatus.context` and
  `ParticipantStatus.tracking_id` from `str | None` to `OptionalNonEmptyString`.

Error message updated: tests that previously asserted field-prefixed messages
(e.g., "object_id must be a non-empty string") now assert the shared message
"must be a non-empty string" (which the `AfterValidator` in `_non_empty` raises).

New tests added: `test_case_status.py`, extended `test_case_participant.py`,
extended `test_vulnerability_record.py`. 860 tests pass.

Note: `CaseParticipant.set_name_if_empty` model validator automatically
populates `name` from `attributed_to` when `name=None`; tests for `name=None`
must omit `attributed_to` to observe the None value.
