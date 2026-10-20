---
source: SPEC-RETIRE-RSH-05-003
timestamp: '2026-10-20T20:12:49.755433+00:00'
title: Retired requirement RSH-05-003
type: implementation
---

Retired RSH-05-003 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). A refused update adopts nothing, so the canonical CaseStatus write does not run for it.

Replacement: RSH-09-002

Final text: `plan/retired-specs/RSH-05-003.md`.
