---
source: SPEC-RETIRE-CLP-12-001
timestamp: '2026-11-02T16:13:01.150775+00:00'
title: Retired requirement CLP-12-001
type: implementation
---

Retired CLP-12-001 from `specs/case-ledger-processing.yaml` (#5358).

Why: It required the validator to accept a CASE_MANAGER-authored Add(CaseStatus) entry, through `_CASE_AUTHORED_SIGNATURES`, a set the validator never reads: the validator accepts every registered signature whoever authored it, so the rule constrained nothing. Who may author an act is decided by sender entitlement at receipt (HP-01-006, HP-01-007) and by the role gate at commit (CLP-09-001); the set is deleted.

Replacement: CLP-09-001

Final text: `plan/retired-specs/CLP-12-001.md`.
