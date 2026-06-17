---
source: ISSUE-753
timestamp: '2026-06-10T17:59:58.244028+00:00'
title: Consolidate report prioritization sender-side BT
type: implementation
---

## Issue #753 — Consolidate EmitEngageCaseActivity and EmitDeferCaseActivity into SenderSideBT pattern

Refactored report prioritization to use a shared sender-side sequence that resolves report addressees, emits the engage/defer activity, and queues it through the common outbox path.

PR: [#886](https://github.com/CERTCC/Vultron/pull/886)
