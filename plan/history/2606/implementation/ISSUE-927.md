---
source: ISSUE-927
timestamp: '2026-06-15T17:22:12.234826+00:00'
title: Sender-side trigger CaseActor routing audit
type: implementation
---

## Issue #927 — Audit sender-side trigger use cases: all participant-originated case-scoped activities must route through CaseActor

Implemented a sender-side routing audit/fix sweep so case-scoped participant-originated trigger activities route only to the CaseActor. Updated report trigger emit routing, suggest-actor trigger routing, trigger activity adapter/port contract, and trigger/router/service coverage to assert single-recipient CaseActor `to` fields across sender-side paths.

PR: <https://github.com/CERTCC/Vultron/pull/958>
