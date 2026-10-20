---
source: SPEC-RETIRE-RSH-05-019
timestamp: '2026-10-20T20:14:08.436088+00:00'
title: Retired requirement RSH-05-019
type: implementation
---

Retired RSH-05-019 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). The PXA acceptance rule moved unchanged into the whole-status rule.

Replacement: RSH-09-005

Final text: `plan/retired-specs/RSH-05-019.md`.
