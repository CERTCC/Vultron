---
source: ISSUE-1707
timestamp: '2026-08-03T19:09:05.650022+00:00'
title: extract _SendEmbargoActivityBase for embargo emit nodes
type: implementation
---

## Issue #1707 — refactor(bt): extract _SendEmbargoActivityBase for factory-dispatch pattern

Created `_SendEmbargoActivityBase` in new `vultron/core/behaviors/embargo/nodes/emit.py`, implementing the shared guard/factory-dispatch/outbox-write skeleton per BTND-07-005. Refactored `SendAnnounceEmbargoEventNode` (best-effort) and `SendTerminateEmbargoActivityNode` (fail-fast BT-14-001) to inherit from the base. Updated architecture ratchet. Added 7 contract tests.

PR: <https://github.com/CERTCC/Vultron/pull/1939>
