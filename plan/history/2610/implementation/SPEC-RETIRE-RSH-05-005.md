---
source: SPEC-RETIRE-RSH-05-005
timestamp: '2026-10-20T20:13:01.714001+00:00'
title: Retired requirement RSH-05-005
type: implementation
---

Retired RSH-05-005 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). Any refused rule refuses the whole update; the indistinguishable-from-current test is gone.

Replacement: RSH-09-002

Final text: `plan/retired-specs/RSH-05-005.md`.
