---
source: SPEC-RETIRE-RSH-05-001
timestamp: '2026-10-20T20:12:38.281997+00:00'
title: Retired requirement RSH-05-001
type: implementation
---

Retired RSH-05-001 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). Per-dimension partial accept is retired.

Replacement: RSH-09-001

Final text: `plan/retired-specs/RSH-05-001.md`.
