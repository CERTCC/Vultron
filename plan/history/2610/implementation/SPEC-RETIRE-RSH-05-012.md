---
source: SPEC-RETIRE-RSH-05-012
timestamp: '2026-10-20T20:13:34.160084+00:00'
title: Retired requirement RSH-05-012
type: implementation
---

Retired RSH-05-012 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). The ledger_payload_object_override contract is removed with its producers.

Final text: `plan/retired-specs/RSH-05-012.md`.
