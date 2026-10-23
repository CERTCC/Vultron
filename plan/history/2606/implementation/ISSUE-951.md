---
source: ISSUE-951
timestamp: '2026-06-15T16:36:50.977840+00:00'
title: Demo Integration CI diagnostic runbook
type: implementation
---

## Issue #951 — Track C: Write Demo Integration CI diagnostic runbook

Created `notes/demo-ci-diagnostics.md` with:

- 3-layer diagnostic model (Sent / Received / Committed) with logger names
  and log patterns for each layer
- Per-invariant diagnostic map covering all 14 case-ledger invariants with
  current xfail status and resolving issue numbers
- Copy-paste-ready local Docker run workflow
- CI artifact interpretation guide (two-actor-case-logs + demo-container-logs)
- Diagnostic checklist for quick reference

Also added a one-line reference to `test/AGENTS.md` pointing to the new file
per the acceptance criteria.

PR: [#957](https://github.com/CERTCC/Vultron/pull/957)
