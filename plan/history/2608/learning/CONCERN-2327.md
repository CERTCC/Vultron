---
source: CONCERN-2327
timestamp: '2026-08-21T16:11:40.487834+00:00'
title: 'GHA matrix boolean coercion — two distinct if: failure modes'
type: learning
---

In `.github/workflows/demo-integration.yml`, the matrix field `full_suite_only`
was declared as a YAML boolean (`false`/`true`) and referenced in job `if:`
conditions: `if: github.event_name != 'pull_request' || matrix.full_suite_only == false`.

Two distinct failure modes exist when a boolean matrix field is referenced in a
GitHub Actions `if:` expression:

(1) **Job-level `if:`**: the `matrix` context does not exist before matrix
expansion — GitHub rejects the entire workflow with a silent startup failure,
zero jobs scheduled, no logs. This broke demo-integration.yml for 116
consecutive runs (DEMOCI-06-004, ISSUE-2118).

(2) **Step-level `if:`**: the `matrix` context IS available, but GitHub coerces
JSON boolean `false` to the string `"false"`, making `matrix.full_suite_only ==
false` always evaluate to `false`. The minimum-PR-set split would be silently
defeated.

The fix (PR #2118) moved filtering into a `scenarios` pre-filter job using
`jq 'select(.full_suite_only == false)'`. `jq` handles JSON booleans natively —
no coercion issue. DEMOCI-06-004, DEMOCI-06-007, DEMOCI-06-008 document the
current approach.

**Resolved**: 2026-08-21 — implementation tracked in #2460.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2459>.
