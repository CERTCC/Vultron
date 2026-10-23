---
source: PAD-design-session-26050501
timestamp: '2026-05-05T16:09:25.793376+00:00'
title: 'Parallel Agentic Development: GitHub Issue-based coordination'
type: idea
---

## Parallel Agentic Development — Design Notes

Design session captured in wip_notes/parallel-agentic-development.md.
Covers migrating from a single-developer, file-based task model
(IMPLEMENTATION_PLAN.md) to a GitHub Issues-based coordination model
supporting multiple parallel AI agents and human developers.

Core decisions:

- GitHub Issues are the coordination primitive (native assignment, labels,
  PR linking, dependency notation)
- PRIORITIES.md remains the authoritative priority ordering; agents MUST NOT
  write to it
- Branch existence (task/<N>-slug) is the distributed claim lock
- No claimed label — branch alone is the lock to avoid dual-source-of-truth
- Stale-claim threshold: 3 days
- Diff-size thresholds: <=50 lines = S, 51-300 = M, 301+ = L
- Code review: single pass with [BLOCKING]/[ADVISORY] tags
- CODEOWNERS already exists; no action needed

Skills updated: build, ingest-idea, review-priorities, study-project-docs,
update-plan.

**Processed**: 2026-05-05 — design decisions captured in
specs/parallel-development.yaml (PAD-01 through PAD-15) and
notes/parallel-development.md. IMPLEMENTATION_PLAN.md converted to
read-only index. GitHub Issues created for all deferred items (#422-#431).
