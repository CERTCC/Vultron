---
source: SPEC-RETIRE-RSH-05-022
timestamp: '2026-10-20T20:14:26.253381+00:00'
title: Retired requirement RSH-05-022
type: implementation
---

Retired RSH-05-022 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). The refused-outcome rule is unchanged in substance; it moved out of the retired group.

Replacement: RSH-09-008

Final text: `plan/retired-specs/RSH-05-022.md`.
