---
source: CONCERN-2011
timestamp: '2026-08-06T17:41:56.879189+00:00'
title: PAD-03 still named archived plan/PRIORITIES.md as authoritative, contradicting
  rewritten PD-06
type: learning
---

## Problem

PR #2006 rewrote `PD-06-004`/`PD-06-005` so that priority ordering is "the sole
responsibility of the `Schedule` field (Now/Next/Later/Someday) on GitHub
Project #24" — `plan/PRIORITIES.md` was archived in `51fa5aee4`.

`specs/parallel-development.yaml` was not updated, so the registry held two
contradictory MUSTs:

- `PAD-03-001` (MUST) — "PRIORITIES.md MUST remain the authoritative ordering document for work priority."
- `PAD-03-002` (MUST_NOT) — "Agents MUST NOT write to PRIORITIES.md."
- `PAD-03-003` (MUST) — "When the `build` skill selects a task, it MUST read PRIORITIES.md once..."

Additionally, 16 other PAD entries across PAD-01, PAD-02, PAD-08, PAD-09, PAD-12,
and PAD-13 still referenced `PRIORITIES.md` or `group:` labels that were retired
in June 2026.

## Root Cause

PR #693 retired PRIORITIES.md from tooling and notes; PR #2006 updated PD-06 in
specs; but `specs/parallel-development.yaml` was never synchronized. This created
a live contradiction between PD-06-004/005 and PAD-03.

## Lessons

- When retiring a file or label, audit ALL specs for bare-filename references.
  `MS-15` (`_check_phantom_paths`) only catches backtick-quoted tokens with a path
  separator — bare filenames like `PRIORITIES.md` and bare label names like
  `group:unscheduled` pass silently.
- Incremental spec updates that fix one half of a cross-spec reference must also
  fix the other half in the same PR, or create a follow-up Concern immediately.

**Resolved**: 2026-08-06 — implementation tracked in #2036.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2035>.
Spec: `specs/parallel-development.yaml`.
