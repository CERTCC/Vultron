---
source: NOTES-user-story-catalog--implementation-tasks
timestamp: '2026-11-04T02:52:37.988289+00:00'
title: 'User story catalog: implementation tasks and related work'
type: note
---

**Archived:** 2026-11-04
**Reason:** delivered — every tracked Task is closed by #5808 (the last part of #4516) and Epic #2717 is closed
**Superseded by:** notes/user-story-catalog.md (now `kind: guidance`), docs/reference/user_stories/ (generated table and traceability matrix)

---

## Implementation Tasks

Created 2026-10-12 under Epic #2717, in dependency order; each is blocked by the
ones it reads from.

| Task | Does | Runs after |
|---|---|---|
| #4506 | Generated table and matrix, cited-story-exists lint, `story-gaps` report, TRACE spec amendments | — |
| #4507 | Persona hierarchy in the glossary, seed `story_2026` pages, support level retired | #4506 |
| #4514 | Per-file advisory for project and process requirements with no story | #4507 |
| #4508 | Drafting: core protocol text | #4507, #4483 |
| #4510 | Drafting: ledger and replication | #4507, #4484 |
| #4512 | Drafting: case management and state machines | #4507, #4484 |
| #4513 | Drafting: implementation architecture | #4507, #4485 |
| #4516 | Split catch-all stories 088, 045, 014 | the four drafting Tasks |
| #4517 | Gate covers `MUST_NOT`; last suppressions retired | the four drafting Tasks |

## Relation to other work under the Epic

- **#4483–#4486** (rationale backfill by area) are complete; see above.
  Where a contributor or maintainer seed story fits a project or process
  requirement they touch, they may cite it; the rationale is still the reason.
- **#4482** (rationale rule) and **#4315** (PR-only growth
  guards replacing the count ceilings) build the helper the project/process
  story advisory reuses, so a guard is written once.
- **#3601** (adjudicating suppressed protocol specs) was to hand the five Ideas
  their worklists by hand. With the Ideas closed by this plan and the gap report
  in place, its hand-off acceptance criteria point at the area Tasks instead;
  its per-spec verdicts remain its own and are recorded in the Tasks' PRs when
  an area reaches them first.
- **#4481** (link-type meaning and direction) does not touch `stories:`, which
  is a field of its own (ADR-0072), not a `rel_type`.
