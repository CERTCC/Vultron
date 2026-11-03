---
source: SPEC-RETIRE-SM-05-004
timestamp: '2026-11-03T15:51:43.352554+00:00'
title: Retired requirement SM-05-004
type: implementation
---

Retired SM-05-004 from `specs/state-machine.yaml` (#5469).

Why: By design case_statuses holds full CaseStatus objects and ledger entries carry payload snapshots, so a reference-only state log is not the design.

Final text: `plan/retired-specs/SM-05-004.md`.
