---
source: SPEC-RETIRE-RSH-05-024
timestamp: '2026-10-20T20:15:28.358307+00:00'
title: Retired requirement RSH-05-024
type: implementation
---

Retired RSH-05-024 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). The tree-structural fault rule is unchanged; it moved out of the retired group.

Replacement: RSH-09-007

Final text: `plan/retired-specs/RSH-05-024.md`.
