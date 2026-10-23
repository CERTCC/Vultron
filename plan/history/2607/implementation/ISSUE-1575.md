---
source: ISSUE-1575
timestamp: '2026-07-22T14:48:32.362834+00:00'
title: Spec corpus formatting and content cleanup
type: implementation
---

## Issue #1575 — Spec corpus formatting and content cleanup

Fixed formatting inconsistencies and minor content problems across 12 spec YAML files.

**Table-breaking YAML fixed**: 80+ specs in `architecture.yaml`, `code-style.yaml`, `datalayer.yaml`, `docs-build-workflow.yaml`, and `participant-role-management.yaml` had embedded or trailing newlines from `>` block scalars (changed to `>-`) and single-quoted strings with blank lines before closing `'` (blank lines removed). A follow-on fix addressed trailing spaces from `'` on its own indented line — moved closing quote to end of last content line.

**Group title cleanup**: Stripped 26 legacy modality suffixes `(MUST/SHOULD/MAY)` from group titles across 6 files; removed embedded spec IDs from CM-11 and CM-12 group titles in `case-management.yaml`.

**PD-09-004/005 rewrite**: Removed internal epic/issue number references (#788, #888, #923, #792) from rationale fields while preserving all normative guidance and causal reasoning.

Registry loads 2084 specs from 68 files. Full test suite: 5302 passed, 39 skipped, 2 xfailed.

PR: <https://github.com/CERTCC/Vultron/pull/1589>
