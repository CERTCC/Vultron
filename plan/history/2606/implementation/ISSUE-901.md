---
source: ISSUE-901
timestamp: '2026-06-11T19:33:29.122549+00:00'
title: SYNC integration single-peer CaseLogEntry replication
type: implementation
---

## Issue #901 — SYNC Integration: happy-path single-peer CaseLogEntry replication

Added integration coverage for the SYNC happy path using two isolated FastAPI apps and a shared _TestASGIRouter. The new test verifies CaseActor append -> Announce(CaseLogEntry) delivery -> peer append, and asserts replicated CaseLogEntry content/hash/index plus distinct DataLayer instances per actor.

PR: [#905](https://github.com/CERTCC/Vultron/pull/905)
