---
source: ISSUE-1651
timestamp: '2026-07-24T18:47:15.971768+00:00'
title: 'New-scenario issue template: enumerate all required update sites'
type: implementation
---

## Issue #1651 — New-scenario issue template: enumerate all required update sites

Added `.github/ISSUE_TEMPLATE/new_demo_scenario.md` — a GitHub issue template
covering all 8+ required update sites when adding a new multi-actor demo scenario:
scenario script, CLI registration, scenario README, both CI matrix jobs (with
`test_file` field), VALID_SCENARIOS shell script, invariant test file, spec entries
(DEMOMA-16), docker README, and demo-future-ideas note. The same-PR rule
(DEMOCI-03-002, DEMOCI-03-004) is called out prominently in the checklist header.

PR: <https://github.com/CERTCC/Vultron/pull/1693>
