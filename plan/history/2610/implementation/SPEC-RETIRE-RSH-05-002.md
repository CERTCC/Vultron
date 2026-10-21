---
source: SPEC-RETIRE-RSH-05-002
timestamp: '2026-10-20T20:12:44.303554+00:00'
title: Retired requirement RSH-05-002
type: implementation
---

Retired RSH-05-002 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). Refused dimensions are no longer carried forward into a recorded status.

Replacement: RSH-09-001

Final text: `plan/retired-specs/RSH-05-002.md`.
