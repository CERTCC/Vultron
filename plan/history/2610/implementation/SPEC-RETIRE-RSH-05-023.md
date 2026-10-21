---
source: SPEC-RETIRE-RSH-05-023
timestamp: '2026-10-20T20:14:32.045100+00:00'
title: Retired requirement RSH-05-023
type: implementation
---

Retired RSH-05-023 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). The EM acceptance rule moved unchanged into the whole-status rule.

Replacement: RSH-09-005

Final text: `plan/retired-specs/RSH-05-023.md`.
