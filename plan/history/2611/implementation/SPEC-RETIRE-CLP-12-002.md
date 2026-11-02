---
source: SPEC-RETIRE-CLP-12-002
timestamp: '2026-11-02T16:11:49.336835+00:00'
title: Retired requirement CLP-12-002
type: implementation
---

Retired CLP-12-002 from `specs/case-ledger-processing.yaml` (#5358).

Why: It required _CASE_AUTHORED_SIGNATURES to list every pair the CASE_MANAGER authors at case creation, but the ledger validator never reads that set, so the rule constrained nothing. Who may author an act is decided by sender entitlement at receipt (HP-01-006, HP-01-007) and by the role gate at commit (CLP-09-001); the set is deleted.

Replacement: CLP-09-001

Final text: `plan/retired-specs/CLP-12-002.md`.
