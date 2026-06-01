---
source: ISSUE-437
timestamp: '2026-06-01T18:33:06.126877+00:00'
title: Enforce spec vs. ADR delineation guidelines (MS-11)
type: implementation
---

## Issue #437 — Enforce spec vs. ADR delineation guidelines (MS-11)

Implemented all four acceptance criteria to make MS-11 actionable for agents
and reviewers:

**AC-1 — Skill guidance**: Added explicit ADR decision paragraphs to both
`.agents/skills/ingest-idea/SKILL.md` and `.agents/skills/learn/SKILL.md`,
directing agents to apply the MS-11 decision-tree heuristic in
`notes/specs-vs-adrs.md` when writing new spec entries.

**AC-2 — AGENTS.md link**: The Change Protocol section now links to
`notes/specs-vs-adrs.md` (MS-11-001 through MS-11-006) so agents can locate
the heuristic without hunting through spec files.

**AC-3 — Spec registry linter**: Added `_check_adr_references()` to
`vultron/metadata/specs/lint.py` that emits advisory `[WARN]` when a spec
rationale references `ADR-NNNN` but no matching file exists in `docs/adr/`.
Added `DANGLING_ADR_REF` to `LintWarningCode` enum. Check is non-blocking,
suppressible via `lint_suppress: [dangling_adr_ref]`, and degrades
gracefully when `docs/adr/` is absent. Covered by 6 new tests.

**AC-4 — ADR template**: Updated `docs/adr/_adr-template.md` More Information
section to prompt authors to list generated spec IDs per MS-11-004.

PR: [#648](https://github.com/CERTCC/Vultron/pull/648)
