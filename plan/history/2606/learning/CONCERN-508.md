---
source: CONCERN-508
timestamp: '2026-06-03T18:56:36.630074+00:00'
title: semantic_registry.py is a 783-line centralized dispatch table with tight coupling
type: learning
---

## Summary

`vultron/semantic_registry.py` is a single 783-line module that consolidates all
`MessageSemantics` → handler wiring. Every new message type requires editing this
file, creating a central point of coupling and a recurring source of merge conflicts.

## Category

- [x] Technical debt

## Severity

medium

## Evidence

- `vultron/semantic_registry.py` (783 lines)

## Impact if Ignored

Any new message type requires editing this file; tight coupling can cause merge
conflicts and makes it harder to understand the scope of a change.

## Suggested Action

Consider splitting the registry by domain area (report, case, embargo, actor) once
the registry stabilises. A plugin-style approach with per-domain registration
would reduce the blast radius of individual changes.

**Resolved**: 2026-06-03 — implementation tracked in #702.
Docs PR: <https://github.com/CERTCC/Vultron/pull/703>.
Fix: split into domain sub-modules under `vultron/semantic_registry/` package;
`__init__.py` assembles all sub-module lists in order with UNKNOWN fallback last,
enforced by a runtime ordering assertion. Public API remains backward-compatible.
`vultron/core/AGENTS.md` checklist and pitfall entry updated.
