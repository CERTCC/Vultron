---
source: SPEC-RETIRE-RSH-05-010
timestamp: '2026-10-20T20:13:24.603048+00:00'
title: Retired requirement RSH-05-010
type: implementation
---

Retired RSH-05-010 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). The ledger_payload_object_override key and its producers are removed; BT-17-003 still governs blackboard keys.

Final text: `plan/retired-specs/RSH-05-010.md`.
