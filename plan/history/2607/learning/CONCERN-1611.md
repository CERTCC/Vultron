---
source: CONCERN-1611
timestamp: '2026-07-22T18:28:33.098262+00:00'
title: notes/ flat hierarchy impedes agent-optimized contextual findability as file
  count and size grow
type: learning
---

## Summary

The `notes/` directory has grown to 64 files (21,908 lines total) in a flat hierarchy. The largest file exceeds 2,000 lines. A single flat directory with no topic grouping increasingly hampers agent-optimized contextual findability and makes it hard for contributors to locate the right context quickly.

## Category

Documentation Infrastructure / Developer Experience

## Severity

Medium — growing pain, not a blocker today, but the cost compounds as the repo evolves.

## Evidence

- 64 `.md` files in a single flat `notes/` directory
- 21,908 total lines across those files
- Largest file: `bt-fuzzer-nodes-report-management.md` at 2,189 lines
- No sub-topic grouping; all files discoverable only by filename prefix or grep
- Related maintenance issues already open: #1465 (lint-notes skill for stale-content pruning)

## Impact if Ignored

- Agents and developers increasingly miss relevant context when loading notes
- Larger required context windows to get adequate coverage
- Duplicated notes accumulate undetected across semantically similar files
- As the directory grows, per-file README indexing drifts further from reality

## Key Finding

The root cause is not the flat directory structure but **large files with mixed topic clusters**. Agents must filter through irrelevant content to find the specific context they need. The fix is to split large files at natural topic-cluster boundaries, not to reorganize into subdirectories.

## Resolution Decision

Split the five largest files along topic-cluster boundaries, one file per coherent "load when" scenario. Promote specs-in-hiding (BT-IDM rules) to formal spec requirements. Add PD-01 spec entries capping notes file size at 500 lines and requiring single-topic focus.

**Resolved**: 2026-07-22 — implementation tracked in #1612.
