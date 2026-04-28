---
name: learn
description: >
  Refine, create, and organize specification and design documentation so
  repository docs are concise, consistent, testable, and aligned with current
  priorities. Loads specs and context, analyzes gaps, interviews the user with
  grill-me to align on scope, then writes to specs/, notes/, AGENTS.md, and
  plan/IMPLEMENTATION_PLAN.md before committing. Use when the user asks to
  audit documentation, promote ephemeral notes to durable docs, or align
  specs with current code.
---

# Skill: Learn

**Constraint**: Modify **markdown files only**. Do not modify code or tests.

## Quick Start

1. Invoke the `study-project-docs` skill to load specs and read all context.
2. Analyze documentation for gaps, ambiguity, redundancy, and drift.
3. Invoke the `grill-me` skill to align on scope and decisions — before
   writing anything.
4. Execute documentation updates across `specs/`, `notes/`, `AGENTS.md`,
   and `plan/IMPLEMENTATION_PLAN.md`.
5. Preserve ephemeral insights from `IDEAS.md` and `IMPLEMENTATION_NOTES.md`.
6. Invoke the `format-markdown` skill, then the `commit` skill.

## Workflow

### Phase 1 — Load Specs and Review Context

Invoke the `study-project-docs` skill. It runs `load-specs`, reads all plan/,
docs/adr/, notes/, and AGENTS.md files, and scans vultron/ and test/.

Additionally read `plan/IMPLEMENTATION_HISTORY.md` for recent completed work.

> `IDEAS.md` and `IMPLEMENTATION_NOTES.md` are ephemeral. Any critical insight
> in them **must be preserved elsewhere** before this session ends.

### Phase 2 — Analyze Documentation

Identify:

1. Missing requirements (code exists but no spec).
2. Ambiguous or untestable requirements.
3. Redundant or contradictory requirements across spec files.
4. Drift from current priorities or the actual codebase.
5. Architectural inconsistencies.

Cross-check whether items in `PRIORITIES.md`, `IDEAS.md`, or
`IMPLEMENTATION_NOTES.md` are fully reflected in `specs/`, `notes/`, or
`AGENTS.md`.

### Phase 3 — Interview with Grill-Me

Invoke the `grill-me` skill. Resolve one question at a time (using `ask_user`)
with a recommended answer before writing anything:

- Which gaps are most important to address in this run?
- Which ephemeral insights should be promoted, and to which durable file?
- Are there unresolvable conflicts that need a human decision?
- Does any spec change require code verification first?

Answer questions from codebase exploration where possible; ask the user only
when the answer cannot be determined from code or existing docs.

### Phase 4 — Refine Specifications (`specs/`)

- Clarify, split, merge, or remove requirements; keep each atomic, specific,
  concise, and verifiable.
- `specs/` are for *what*, not *how*.
- Eliminate redundancy; use `PROD_ONLY` tag for production-only requirements.
- Update `specs/README.md` to reflect all file additions, removals, renames,
  and topic reorganizations.

### Phase 5 — Update Design Notes (`notes/`)

- Capture design insights, tradeoffs, and lessons learned; do not duplicate
  spec text.
- Promote critical insights from `IMPLEMENTATION_NOTES.md`.
- Mark unresolved items explicitly: `Open Question:` / `Design Decision:`.
- Update `notes/README.md` when files are added, removed, or reorganized.
- Every `notes/*.md` (except `notes/README.md`) must have valid YAML
  frontmatter with at least `title` and `status`.

### Phase 6 — Capture Implementation Tasks

Add to `plan/IMPLEMENTATION_PLAN.md` only specific, actionable, testable tasks
not already tracked. No priority indicators; no design notes or open questions.

### Phase 7 — Update Agent Guidance (`AGENTS.md`)

Add or refine recurring implementation guidance: precise, actionable, and
minimal. Document patterns, conventions, and process rules useful for future
agents.

### Phase 8 — Preserve Ephemeral Insights

For items in `IDEAS.md` or `IMPLEMENTATION_NOTES.md` now captured elsewhere,
apply line-level strikethrough to the original text and add a reference:

```markdown
~~Original idea text~~
→ captured in specs/foo.yaml
```

Do **not** delete the original text. Do **not** reference these ephemeral
files from durable docs.

### Phase 9 — Lint and Commit

1. Invoke the `format-markdown` skill (`./mdlint.sh`) on all new/modified
   markdown files. Fix all errors.
2. If a requirement conflict cannot be resolved, add a note to
   `plan/IMPLEMENTATION_NOTES.md` and **stop before committing**.
3. Invoke the `commit` skill. Use multiple commits for thematically distinct
   changes (e.g., spec refactoring, insights promoted, AGENTS.md updates).

## Constraints

- Do not modify code or tests.
- Do not skip the grill-me phase — it must complete before any writing.
- Do not reference `IDEAS.md` or `IMPLEMENTATION_NOTES.md` from durable docs.
- Verify assumptions against the codebase; do not assert absence without
  evidence.
