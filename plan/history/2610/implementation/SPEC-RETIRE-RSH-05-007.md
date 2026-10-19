---
source: SPEC-RETIRE-RSH-05-007
timestamp: '2026-10-19T18:45:47.572823+00:00'
title: Retired requirement RSH-05-007
type: implementation
---

Retired RSH-05-007 from `specs/received-status-handling.yaml` (#4295).

Why: Replicas copy what each entry carries (CM-23-016, ADR-0124): carrying the replica's own RM forward over an entry's is reading local state to fill a field, which CM-23-016 forbids. The CASE_MANAGER never commits a regression, so in ledger order the ratchet only ever made a diverged replica disagree further.

Replacement: CM-23-016

Final text: `plan/retired-specs/RSH-05-007.md`.
