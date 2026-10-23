---
source: CONCERN-514
timestamp: '2026-06-04T13:12:34.045887+00:00'
title: Split case BT nodes into nodes/ subpackage by semantic domain
type: learning
---

## Summary

`vultron/core/behaviors/case/nodes.py` was the highest-churn source file in
the repository at 1502 lines, 13 BT node classes, and 47 commits in 90 days.
Every change to any workflow step required touching the same monolithic module,
making code review shallow and increasing regression risk (including the
silent-duplicate-method pitfall already documented in AGENTS.md).

## Category

- [x] Fragile / high-churn area

## Severity

medium

## Root Cause

All case-protocol BT nodes live in one flat module. Any change — regardless of
which workflow step it touches — modifies the same file, making code review
shallow and raising the risk that duplicate method definitions silently shadow
correct logic (an existing AGENTS.md pitfall).

## Resolution

**Resolved**: 2026-06-03 — implementation tracked in #736.

Docs PR: <https://github.com/CERTCC/Vultron/pull/737>.

- Added `specs/behavior-tree-node-design.yaml` BTND-07 group with two new
  requirements (BTND-07-001, BTND-07-002) formalizing the "one concern per
  module" rule for BT node packages and mirrored test structure.
- Added AGENTS.md pitfall entry: "Flat `nodes.py` with 10+ BT Classes Is a
  Code Smell" with refactoring guidance referencing BTND-07-001 and
  BTND-07-002.
- Implementation issue #736 created as child of epic #539, blocked by concern
  #514, added to Project #24 with Schedule=Someday.
