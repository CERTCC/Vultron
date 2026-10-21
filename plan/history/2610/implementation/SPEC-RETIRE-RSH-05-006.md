---
source: SPEC-RETIRE-RSH-05-006
timestamp: '2026-10-20T20:13:07.731278+00:00'
title: Retired requirement RSH-05-006
type: implementation
---

Retired RSH-05-006 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). RM.CLOSED stays terminal for every status a closed participant sends.

Replacement: RSH-09-003

Final text: `plan/retired-specs/RSH-05-006.md`.
