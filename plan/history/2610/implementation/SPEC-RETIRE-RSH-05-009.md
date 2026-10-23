---
source: SPEC-RETIRE-RSH-05-009
timestamp: '2026-10-20T20:13:19.755846+00:00'
title: Retired requirement RSH-05-009
type: implementation
---

Retired RSH-05-009 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). With no adjudication patch there is no snapshot shape to preserve; the entry records the received object.

Replacement: RSH-09-001

Final text: `plan/retired-specs/RSH-05-009.md`.
