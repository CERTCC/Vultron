---
source: CONCERN-506
timestamp: '2026-06-03T19:25:49.127772+00:00'
title: Architecture notes describe target layout as well as current structure, creating
  onboarding confusion
type: learning
---

## Summary

Several notes files (notably `notes/architecture-ports-and-adapters.md`) and
`AGENTS.md` described both the target architecture and the current state
without clearly distinguishing between them. New contributors and agents may
confuse aspirational layout with what actually exists today.

## Category

- Technical debt

## Severity

medium

## Evidence

- `notes/architecture-ports-and-adapters.md`
- `AGENTS.md`

## Impact if Ignored

New contributors implement code in the wrong layer or against a layout that
does not yet exist, requiring rework and creating further drift.

## Root Cause

Two distinct gaps:

1. `notes/architecture-ports-and-adapters.md` was marked `status: superseded`
   after concern #658 split it into three focused files (`architecture-hexagonal.md`,
   `architecture-ports.md`, `architecture-adapters.md`), but the file was never
   moved to `archived_notes/`. Superseded files left in `notes/` pollute the
   directory for agents and risk outdated guidance being loaded as active context.

2. The active file `notes/architecture-adapters.md` had two "Future" sections
   (`Future delivery stubs` and `Future: ActorScopedDataLayer protocol`) using
   vague language with no references to the GitHub issues tracking those items.

## Resolution

**Resolved**: 2026-06-03 — implementation tracked in #705.

- Moved `notes/architecture-ports-and-adapters.md` → `archived_notes/` via
  `git mv`; updated `archived_notes/README.md` with archive entry.
- Updated `notes/architecture-adapters.md`: "Future delivery stubs" section
  now references #650; "Future: ActorScopedDataLayer" now references #655.
- Added `AGENTS.md` pitfall: superseded `notes/*.md` files must be moved
  to `archived_notes/`, not left in `notes/`.
- Added `specs/project-documentation.yaml` PD-03-004 and PD-03-005 (MUST
  move superseded files promptly; MUST update `archived_notes/README.md`).
- Fixed PD-03-002 path: `docs/archived_notes/` → `archived_notes/`.
- Updated `.agents/skills/condense-agents-md/REFERENCE.md` to point to
  current successor files.

Docs PR: <https://github.com/CERTCC/Vultron/pull/706>.
Implementation tracked in #705.
