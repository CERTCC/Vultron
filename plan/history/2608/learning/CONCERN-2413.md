---
source: CONCERN-2413
timestamp: '2026-08-24T15:08:29.202734+00:00'
title: No sibling-scan step in bug-fix workflow — same root cause recurs in peer files
type: learning
---

## Summary

When a bug is fixed in one scenario or file, there is no process step requiring
the developer to check whether the same root cause exists in peer scenarios or
files before closing the issue. The same underlying bug recurs in sibling
locations and is filed as a separate issue.

## Surface Symptom vs. Underlying Problem

**Surface symptom:** Near-duplicate bugs appear in the backlog; fixes that look
complete turn out to leave sibling instances open.

**Underlying problem:** The bug-fix workflow has no "where else does this pattern
appear?" gate. A developer who finds and fixes the bug in the first location they
look naturally stops there — the workflow offers no prompt to look further. This
is a process gap, not a code gap.

## Evidence

- #2324 — "case owner closes last" rule applied when fixing `fvcv_handoff_demo`,
  but `fccv_extension_demo` and `fvcv_extension_demo` had the same ordering bug
  and were not checked at fix time
- #1766 — UUID adoption fix applied to one actor-creation path; peer paths not
  checked at fix time
- Pattern identified in RCA (2026-08-19) as "Fix one, miss the siblings": a
  recurring backlog inflation mechanism

**Resolved**: 2026-08-24 — bugfix skill redesigned with investigate-first flow
and mandatory sibling-scan step (Phase 2d). `specs/bugfix-workflow.yaml` and
`notes/bugfix-workflow.md` deleted; background context moved to
`.claude/skills/bugfix/REFERENCE.md`. AGENTS.md pitfall added.

Docs PR: <https://github.com/CERTCC/Vultron/pull/2509>.
