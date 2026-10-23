---
source: ISSUE-728
timestamp: '2026-06-04T18:45:43.482978+00:00'
title: 'Refactor #699 step 5: migrate CaseParticipant + role subclasses to core'
type: implementation
---

## Issue #728 — Refactor #699 step 5: migrate CaseParticipant + role subclasses to core

Migrated `CaseParticipant` and all 8 role subclasses (`FinderParticipant`,
`ReporterParticipant`, `FinderReporterParticipant`, `VendorParticipant`,
`DeployerParticipant`, `CoordinatorParticipant`, `OtherParticipant`,
`CaseActorParticipant`) from the wire layer
(`vultron/wire/as2/vocab/objects/case_participant.py`) to the core layer
(`vultron/core/models/case_participant.py`).

Key outcomes:

- New canonical core module `vultron/core/models/case_participant.py` with
  `CaseParticipant(CoreObject)` + 8 role subclasses + `VultronParticipant` alias
- `vultron/core/models/participant.py` converted to re-export shim
- Wire module re-exports core subclasses; keeps wire `CaseParticipant(VultronAS2Object)`
  for wire VOCABULARY; `CaseParticipantRef` narrowed to `ActivityStreamRef[CaseParticipant]`
  (wire-only) to satisfy `as_Object` bound on `target` field
- `vultron/core/models/vultron_types.py` exports `CaseParticipant` + all 8 subclasses
- 10 demo files updated to use wire `CaseParticipant(case_roles=[CVDRole.XXX])`
- Wire test fixtures that embed participants inline in `VulnerabilityCase.case_participants`
  now use wire `CaseParticipant(case_roles=[CVDRole.CASE_MANAGER])` to satisfy
  Pydantic runtime validation (core subclasses are not wire subclasses)
- All 4 linters pass: black, flake8, mypy (0 errors), pyright (0 errors/warnings)
- Full test suite: 3053 passed, 0 failed, 0 errors (including integration tests)

**Lesson**: `# type: ignore` and `# pyright: ignore` suppress static checkers
but do NOT fix Pydantic runtime validation. After migration, wire-layer code
must use `CaseParticipant(case_roles=[CVDRole.XXX])`, not core role subclasses,
when constructing objects for wire fields.

PR: [#784](https://github.com/CERTCC/Vultron/pull/784)
