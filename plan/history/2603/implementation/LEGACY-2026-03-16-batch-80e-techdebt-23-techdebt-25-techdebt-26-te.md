---
title: "Batch 80e \u2014 TECHDEBT-23 + TECHDEBT-25 + TECHDEBT-26 + TECHDEBT-28\
  \ (2026-03-16)"
type: implementation
date: '2026-03-16'
source: LEGACY-2026-03-16-batch-80e-techdebt-23-techdebt-25-techdebt-26-te
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1725
legacy_heading: "Batch 80e \u2014 TECHDEBT-23 + TECHDEBT-25 + TECHDEBT-26\
  \ + TECHDEBT-28 (2026-03-16)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-16'
---

## Batch 80e — TECHDEBT-23 + TECHDEBT-25 + TECHDEBT-26 + TECHDEBT-28 (2026-03-16)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1725`
**Canonical date**: 2026-03-16 (git blame)
**Legacy heading**

```text
Batch 80e — TECHDEBT-23 + TECHDEBT-25 + TECHDEBT-26 + TECHDEBT-28 (2026-03-16)
```

**Legacy heading dates**: 2026-03-16

**Tasks completed**: TECHDEBT-23, TECHDEBT-25, TECHDEBT-26, TECHDEBT-28

### What was done

**TECHDEBT-23** — Added `TriggerRequest` base class in
`vultron/core/use_cases/triggers/requests.py` with shared `model_config` and
`actor_id: NonEmptyString`. All 9 concrete trigger request models now inherit
from `TriggerRequest` with duplicate `model_config` and `actor_id` fields
removed.

**TECHDEBT-25** — Created `vultron/core/use_cases/_helpers.py` with
`_as_id(obj) -> str | None` helper that normalises mixed `str | wire-object`
values to a plain string ID. Replaced ~15 scattered `obj.as_id if hasattr(...)`
ternary patterns across `case.py`, `actor.py`, `embargo.py`,
`case_participant.py`, `note.py`, and `status.py`.

**TECHDEBT-26** — Removed the `OptionalNonEmptyString` type alias from both
definition sites (`wire/as2/vocab/base/types.py` and
`core/models/events/base.py`) and all usage sites (5 wire-layer vocab objects,
`core/models/events/base.py`). Replaced with the inline `NonEmptyString | None`
form. Removed the re-export from `core/models/events/__init__.py`. Updated
`specs/code-style.yaml` CS-08-002 accordingly.

**TECHDEBT-28** — Added `_idempotent_create(dl, type_key, id_key, obj, label,
activity_id) -> bool` helper to `_helpers.py`. Replaced the repeated
idempotency-guard-then-create pattern in 10 use-case `execute()` methods
(`CreateEmbargoEvent`, `CreateNote`, `CreateCaseParticipant`, `CreateCaseStatus`,
`CreateParticipantStatus`, `SuggestActorToCase`, `AcceptSuggestActorToCase`,
`OfferCaseOwnershipTransfer`, `InviteActorToCase`, `InviteToEmbargoOnCase`).

**Test results:** 893 passed, 0 failed (unchanged from baseline).
