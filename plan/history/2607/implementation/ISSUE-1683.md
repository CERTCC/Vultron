---
source: ISSUE-1683
timestamp: '2026-07-24T18:51:58.093322+00:00'
title: Filter disposition=rejected entries from report build_timeline
type: implementation
---

## Issue #1683 — Report: filter disposition=rejected entries from output

Added a 2-line guard in `build_timeline` (`if event.disposition != "recorded": continue`) to skip local-only correlation markers before they reach the timeline. These rejected entries had empty `payloadSnapshot` values and produced `—` actor labels and empty target columns in the rendered report.

Changes: `vultron/demo/report.py` (guard + docstring), `specs/demo-report.yaml` (new DRPT-02-007), `test/demo/test_report.py` (2 new tests).

PR: <https://github.com/CERTCC/Vultron/pull/1694>
