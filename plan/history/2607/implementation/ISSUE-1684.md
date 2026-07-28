---
source: ISSUE-1684
timestamp: '2026-07-27T13:54:40.818865+00:00'
title: 'fix(report): extract CS/EM state from caseStatuses array'
type: implementation
---

## Issue #1684 — Report: extract CS/EM state from caseStatuses array in VulnerabilityCase payloads

Fixed `_candidate_dicts` in `vultron/demo/report.py` to iterate items of any
`caseStatuses`/`case_statuses` list found on a visited node. Previously, EM/CS
state carried in the `caseStatuses` array on `VulnerabilityCase` payloads was
never reached, leaving EM and CS columns blank for early timeline rows.

Added 3 tests: camelCase array extraction, snake_case key tolerance, and
corrupt non-list guard.

PR: <https://github.com/CERTCC/Vultron/pull/1705>
