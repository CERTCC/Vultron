---
name: update-plan
description: >
  Perform a gap analysis between current specs/notes and the codebase, then
  create GitHub Issues for any untracked gaps and update PRIORITIES.md
  references as needed. Observations and open questions go directly to
  notes/ files. Use after learn or ingest-idea has updated specs/notes, and
  before running build. Does not write new tasks to IMPLEMENTATION_PLAN.md.
---

# Skill: Update Plan

Perform a gap analysis between the current specifications, design notes, and
the actual codebase, then create GitHub Issues for any untracked gaps.

**Constraint**: Do not write new tasks to `plan/IMPLEMENTATION_PLAN.md` — it
is a read-only index. All new work items MUST be GitHub Issues. Do not change
code, tests, `specs/`, or `notes/` (except when writing gap-analysis
observations). Do **not** write to `plan/BUILD_LEARNINGS.md` — that file is
reserved for `build` and `bugfix`.

**Trigger**: Use after `learn` or `ingest-idea` has updated specs or notes,
to translate those changes into concrete GitHub Issues. Also run periodically
to keep open Issues aligned with the codebase.

## Quick Start

1. Invoke `study-project-docs` to load all specs and context.
2. Run a gap analysis: compare `specs/` + `notes/` against `vultron/` and
   `test/`.
3. For each gap, create a GitHub Issue (group:unscheduled) rather than a plan
   entry.
4. Write any significant observations or open questions directly to the
   appropriate `notes/*.md` file (not to `BUILD_LEARNINGS.md`).
5. Invoke `commit`.

## Workflow

### Phase 1 — Load Context

Invoke the `study-project-docs` skill. It loads all specs, reads all plan/,
docs/adr/, notes/, AGENTS.md, and scans vultron/ and test/.

To understand what has recently been completed and avoid re-adding finished
work, read the current month's index at `plan/history/YYMM/README.md` (where
`YYMM` is the current year-month, e.g. `2604`). Open individual entry files
only when their titles suggest they contain relevant context.

### Phase 1b — Resolve GitHub Issues

Fetch open issues from `CERTCC/Vultron` using `github-mcp-server-list_issues`
(state: `OPEN`). This gives a picture of what work is already tracked. When
writing new gap Issues, check this list to avoid creating duplicates.

### Phase 2 — Gap Analysis

Compare the current `specs/` + `notes/` against `vultron/` and `test/`:

- **Missing implementations**: a spec or note says X should exist, but code
  search finds no implementation.
- **Partial implementations**: code exists but tests or edge cases are
  missing.
- **Untested behaviors**: implementation exists but no test covers it.
- **Stale open Issues**: GitHub Issues for things already implemented — close
  these with a comment explaining they are done.
- **Known bugs**: open entries in `plan/BUGS.md` that block or relate to
  planned work.

> Do not assume missing functionality; confirm via code search first.

### Phase 3 — Create GitHub Issues for gaps

For each confirmed gap, create a GitHub Issue:

```bash
gh issue create --repo CERTCC/Vultron \
  --title "<Gap description — one line>" \
  --body "## Summary

<What is missing and why it matters — one paragraph>

## Acceptance Criteria

- [ ] AC-1: <testable criterion>
- [ ] AC-2: <testable criterion>
...

## Reference

Spec: \`specs/<topic>.yaml\` <ID range>" \
  --label "group:unscheduled,size:<S|M|L>"
```

Set the `size:` label from AC count: 1–2 → `size:S`; 3–6 → `size:M`;
7+ → `size:L`.

Do **not** add tasks to `plan/IMPLEMENTATION_PLAN.md`.

### Phase 4 — Write Observations to notes/

- Any gap-analysis observations, open questions, clarified assumptions, or
  architectural risks discovered during gap analysis SHOULD be written
  directly to the appropriate `notes/*.md` file.
- Do **not** write these observations to `plan/BUILD_LEARNINGS.md`.
  That file is reserved for `build` and `bugfix` outputs.

### Phase 5 — Commit

Invoke the `commit` skill. Commit only modified notes/ files with a clear,
specific message (e.g.,
`plan: gap analysis — create N issues, update notes/`).

## Constraints

- Do not modify code or tests.
- Do not write to `plan/BUILD_LEARNINGS.md`.
- Do not write new tasks to `plan/IMPLEMENTATION_PLAN.md`.
- Do not speculate about missing functionality; verify with code search first.
- Do not implement anything — that is `build`'s domain.
- Use `uv run append-history implementation` only via `build` — never from
  within `update-plan`.
