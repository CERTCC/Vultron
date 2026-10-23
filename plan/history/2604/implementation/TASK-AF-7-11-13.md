---
title: "AF.7, AF.11, AF.13 — Architecture boundary test, type alias cleanup, AGENTS.md"
type: implementation
timestamp: '2026-04-30T21:06:17+00:00'

source: TASK-AF-7-11-13
---

## TASK-AF AF.7, AF.11, AF.13

Completed three subtasks of TASK-AF (Activity Factory Pattern).

### AF.7 — Architecture boundary test (ratchet pattern)

Created `test/architecture/__init__.py` and
`test/architecture/test_activity_factory_imports.py`.
The test enforces that only `vocab/activities/`, `factories/`,
`test/wire/as2/vocab/`, and `test/architecture/` may import directly from
`vultron.wire.as2.vocab.activities`. All other files are captured as
`KNOWN_VIOLATIONS` (47 entries — AF.8–10 migration debt). The test fails
both on new violations and on resolved violations not yet removed from the set.

### AF.11 — Remove vestigial TypeAliases

- `report.py`: deleted `OfferRef`; removed `TypeAlias` + `ActivityStreamRef` imports.
- `case.py`: deleted `RmInviteToCaseRef`; removed `TypeAlias` + `ActivityStreamRef` imports.
- `embargo.py`: renamed `EmProposeEmbargoRef` → `_EmProposeEmbargoRef` (file-private).

### AF.13 — AGENTS.md factory boundary note

Added "Constructing Outbound Activities" subsection to AGENTS.md Quick
Reference documenting that code outside `vocab/activities/` and `factories/`
MUST use factory functions, enforced by the architecture test.

### Supporting fix — test_embargo_factories.py

Removed internal `ChoosePreferredEmbargoActivity` import; replaced
`isinstance` checks and attribute accesses with `as_Question` + `getattr`.

### Outcome

2181 passed, 12 skipped. All linters clean.
