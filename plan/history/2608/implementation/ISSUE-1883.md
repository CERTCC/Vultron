---
source: ISSUE-1883
timestamp: '2026-08-08T01:45:16.535612+00:00'
title: 'feat: migrate core/behaviors/ Ports (1/5) — trivial base-only reparent'
type: implementation
---

## Issue #1883 — Migrate core/behaviors/ Ports (1/5): trivial base-only reparent

Migrated all Type A BT nodes from DataLayerCondition/DataLayerAction to DataLayerConditionWithPorts/DataLayerActionWithPorts across note/, status/, and case/ domains. 30 nodes across 14 source files migrated. Trivial no-op setup() overrides removed from ownership_transfer.py (AC-2). 21 new typed-ports tests added across 3 new test files (AC-4). All 1677 unit tests pass.

PR: <https://github.com/CERTCC/Vultron/pull/2125>
