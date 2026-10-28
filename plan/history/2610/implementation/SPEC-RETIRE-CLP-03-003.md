---
source: SPEC-RETIRE-CLP-03-003
timestamp: '2026-10-28T17:17:54.427223+00:00'
title: Retired requirement CLP-03-003
type: implementation
---

Retired CLP-03-003 from `specs/case-ledger-processing.yaml` (#5326).

Why: ADR-0041 removed the proto-case: no case ledger exists before the CASE_MANAGER creates the case, so report receipt writes no entry. CLP-02-013 already keeps activities processed before a case exists off the ledger, and CLP-07-011 makes the Create(VulnerabilityCase) the genesis entry.

Replacement: CLP-02-013

Final text: `plan/retired-specs/CLP-03-003.md`.
