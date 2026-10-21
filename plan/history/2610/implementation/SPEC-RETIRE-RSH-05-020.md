---
source: SPEC-RETIRE-RSH-05-020
timestamp: '2026-10-20T20:14:14.476385+00:00'
title: Retired requirement RSH-05-020
type: implementation
---

Retired RSH-05-020 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). The entailments are evaluated on the status as received and refuse the whole update.

Replacement: RSH-09-004

Final text: `plan/retired-specs/RSH-05-020.md`.
