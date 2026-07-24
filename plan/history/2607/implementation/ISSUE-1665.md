---
source: ISSUE-1665
timestamp: '2026-07-24T19:58:52.193352+00:00'
title: CI linter enforcement of ECA format for DEMOMA scenario groups
type: implementation
---

## Issue #1665 — Implement CI linter enforcement of ECA format for DEMOMA scenario groups

All four acceptance criteria were already fully implemented by PR #1664 (merged 2026-07-24):

- AC-1: `spec-lint` exits 1 for `scenario_start` groups with no `BehavioralSpec` with steps (`vultron/metadata/specs/lint.py`)
- AC-2: MS-13-004 spec entry in `specs/meta-specifications.yaml`
- AC-3: `.github/workflows/spec-check.yml` runs on `specs/**` changes
- AC-4: Three tests in `test/metadata/specs/test_lint.py`

Issue verified satisfied on current `main` and closed with reference comment.
