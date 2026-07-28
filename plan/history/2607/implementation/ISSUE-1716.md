---
source: ISSUE-1716
timestamp: '2026-07-27T18:40:04.576359+00:00'
title: Decompose AutoCloseBranchNode into precondition + routing + emit BT Sequence
type: implementation
---

## Issue #1716 — Decompose AutoCloseBranchNode into precondition + routing + emit BT Sequence

Replaced `AutoCloseBranchNode` (BT-IDM-03 god node) with a properly decomposed `py_trees.Sequence` of DataLayer-backed leaf nodes per DEMOMA-07-006.

New nodes: `AllParticipantsRMClosedConditionNode`, `CloseNotYetEmittedConditionNode` (in `conditions.py`), `EmitCloseCaseNode` (in `lifecycle.py`).

Module-level `_auto_close_triggered` set and `_auto_close_lock` removed; idempotency now uses the DataLayer outbox (survives restarts, visible to BT audit).

Architecture violation (lifecycle.py importing `_resolve_case_manager_id` from `use_cases`) resolved; `lifecycle.py` removed from `KNOWN_VIOLATIONS`.

PR: <https://github.com/CERTCC/Vultron/pull/1724>
