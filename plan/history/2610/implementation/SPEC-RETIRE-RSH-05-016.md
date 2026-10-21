---
source: SPEC-RETIRE-RSH-05-016
timestamp: '2026-10-20T20:13:56.916507+00:00'
title: Retired requirement RSH-05-016
type: implementation
---

Retired RSH-05-016 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). A refused CaseStatus dimension refuses the whole status; nothing is carried forward.

Replacement: RSH-09-005

Final text: `plan/retired-specs/RSH-05-016.md`.
