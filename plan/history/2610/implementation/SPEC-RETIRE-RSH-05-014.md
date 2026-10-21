---
source: SPEC-RETIRE-RSH-05-014
timestamp: '2026-10-20T20:13:44.376204+00:00'
title: Retired requirement RSH-05-014
type: implementation
---

Retired RSH-05-014 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). The ledger_payload_object_override consumer is removed from CommitCaseLedgerEntryNode.

Final text: `plan/retired-specs/RSH-05-014.md`.
