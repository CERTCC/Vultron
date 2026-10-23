---
source: SPEC-RETIRE-RSH-05-004
timestamp: '2026-10-20T20:12:55.650545+00:00'
title: Retired requirement RSH-05-004
type: implementation
---

Retired RSH-05-004 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). The canonical entry records the status as received; there is no accepted portion to snapshot.

Replacement: RSH-09-001

Final text: `plan/retired-specs/RSH-05-004.md`.
