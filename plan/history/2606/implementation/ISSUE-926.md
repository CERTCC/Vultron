---
source: ISSUE-926
timestamp: '2026-06-15T18:03:15.717816+00:00'
title: CaseActor commit-path uniqueness
type: implementation
---

## Issue #926 — CaseActor commit-path uniqueness

Implemented an idempotent CaseActor commit path so a logical assertion only produces one canonical CaseLedgerEntry, while preserved payload snapshots and fan-out payloads stay identical across recipients.

PR: [#962](https://github.com/CERTCC/Vultron/pull/962)
