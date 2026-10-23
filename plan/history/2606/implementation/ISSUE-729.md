---
source: ISSUE-729
timestamp: '2026-06-04T20:13:16.142810+00:00'
title: Migrate VulnerabilityCase, CaseEvent, CaseReference, CaseActor to core
type: implementation
---

## Issue #729 — Refactor #699 step 6: migrate VulnerabilityCase + CaseEvent + CaseReference + CaseActor to core

Step 6 of the domain object migration (#699). Promoted four types from wire
stubs to full core implementations:

- **`VulnerabilityCase(CoreObject)`** — renamed from `VultronCase(VultronObject)`
  stub; added all domain methods: `add_report`, `add_participant`,
  `remove_participant`, `set_embargo`, `record_activity`, `record_event`,
  `current_status`, `case_status`; `_init_case_statuses` model_validator seeds
  initial `CaseStatus` on construction; `VultronCase` alias preserved
- **`CaseEvent(BaseModel)`** — renamed from `VultronCaseEvent`; stays `BaseModel`
  (inline value object, not federated identity — schema change deferred);
  added `NonEmptyString` fields, `field_validator` for ISO parsing,
  `field_serializer`; `VultronCaseEvent` alias preserved
- **`CaseActor(CoreObject)`** — renamed from `VultronCaseActor(VultronObject)`;
  `type_="Service"` registry mismatch documented; `VultronCaseActor` alias
  preserved
- **`CaseReference(CoreObject)`** — new type with `url`/`name`/`tags` and
  `CASE_REFERENCE_TAG_VOCABULARY` (canonical location moved from wire to core)

Wire layer updated: `case_event.py` → single re-export; `case_actor.py` →
updated import alias; `case_reference.py` → added `from_core`/`to_core`;
`vulnerability_case.py` → updated to `CoreVulnerabilityCase`.

`core/models/events/*.py` (6 files) updated to import via `VulnerabilityCase as
VultronCase` alias. `vultron_types.py` updated to export new canonical names.

84 new unit tests across `test/core/models/test_case*.py`. Existing
`test_core_object.py` AC-4 guard updated (VulnerabilityCase now migrated);
positive assertions added for `VulnerabilityCase` and `VultronCase` alias.

**AC-2 deferred**: wire types keep all methods. Thinning wire projections to
pure projections is deferred to the #699 finale when the DataLayer is also
updated.

All 3000 unit tests pass. Black, flake8, mypy, pyright all clean.

PR: [#787](https://github.com/CERTCC/Vultron/pull/787)
