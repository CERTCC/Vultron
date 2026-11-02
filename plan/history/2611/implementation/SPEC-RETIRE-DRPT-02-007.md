---
source: SPEC-RETIRE-DRPT-02-007
timestamp: '2026-11-02T18:40:42.110513+00:00'
title: Retired requirement DRPT-02-007
type: implementation
---

Retired DRPT-02-007 from `specs/demo-report.yaml` (#5351).

Why: It requires `build_timeline` to skip ledger entries whose `disposition` is not `"recorded"`, but `CaseLedgerEntry` has no `disposition` field and `build_timeline` in `vultron/demo/report.py` filters on none: every replica entry is a canonical case event (CLP-02-004). Inclusion, de-duplication and order of entries are already covered by DRPT-02-004, DRPT-02-015 and DRPT-02-005, so no replacement is needed.

Final text: `plan/retired-specs/DRPT-02-007.md`.
