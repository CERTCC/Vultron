---
name: learn
description: >
  Promote lessons learned from the build process into durable specifications
  and design notes. Reads IMPLEMENTATION_NOTES and IMPLEMENTATION_HISTORY
  (internal sources), analyzes gaps, interviews the user with grill-me to
  align on scope, then writes to specs/, notes/, and AGENTS.md before
  committing. Use when build execution has produced insights that should be
  reflected in specs or notes. For external ideas (IDEAS.md), use ingest-idea
  instead.
---

# Skill: Learn

Integrate lessons learned from build execution into the project's durable
specification and design documentation. The input is what the build process
has discovered (`IMPLEMENTATION_NOTES.md`, `IMPLEMENTATION_HISTORY.md`); the
output is refined `specs/`, `notes/`, and `AGENTS.md`.

**Constraint**: Modify **markdown files only**. Do not modify code or tests.

**Trigger**: Use this skill when `plan/IMPLEMENTATION_NOTES.md` or
`plan/IMPLEMENTATION_HISTORY.md` has grown and those insights should be
promoted into durable docs.

> For new external ideas from `plan/IDEAS.md`, use `ingest-idea` instead.

## Quick Start

1. Read `plan/IMPLEMENTATION_NOTES.md` and `plan/IMPLEMENTATION_HISTORY.md`.
2. Invoke `study-project-docs` for full context (specs, notes, code).
3. Analyze what the build process has learned vs. what specs and notes capture.
4. Invoke `grill-me` to align on scope and decisions — before writing anything.
5. Write to `specs/`, `notes/`, and `AGENTS.md`.
6. Invoke `format-markdown`, then `commit`.

## Workflow

### Phase 1 — Load Internal Sources and Context

1. Read `plan/IMPLEMENTATION_NOTES.md` — open questions, observations, and
   lessons from recent build runs (ephemeral; must be promoted before it's
   lost).
2. Read `plan/IMPLEMENTATION_HISTORY.md` — completed tasks and their recorded
   lessons, for additional context.
3. Invoke the `study-project-docs` skill for full context: specs JSON,
   plan files, docs/adr/, notes/, AGENTS.md, and a code scan.

> `IMPLEMENTATION_NOTES.md` is ephemeral. Any critical insight in it **must
> be promoted** to `specs/` or `notes/` before this session ends.

### Phase 2 — Analyze Gaps

Identify what the build process has learned that is not yet captured in
durable docs:

1. Missing requirements — behavior exists in code but has no spec.
2. Ambiguous or untestable requirements — reality diverges from what's written.
3. Redundant or contradictory requirements across spec files.
4. Agent guidance patterns that keep recurring in `IMPLEMENTATION_NOTES.md`
   but are not yet in `AGENTS.md`.
5. Architectural insights from `IMPLEMENTATION_HISTORY.md` not yet in
   `notes/`.

### Phase 3 — Interview with Grill-Me

Invoke the `grill-me` skill. Resolve one question at a time (using `ask_user`)
with a recommended answer before writing anything:

- Which insights from `IMPLEMENTATION_NOTES.md` are most important to promote?
- Which gaps are most critical to close in this run?
- Are there unresolvable conflicts that need a human decision?
- Does any spec change require code verification first?

Answer questions from codebase exploration where possible.

### Phase 4 — Refine Specifications (`specs/`)

- Clarify, split, merge, or remove requirements; keep each atomic, specific,
  concise, and verifiable.
- `specs/` are for *what*, not *how*.
- Eliminate redundancy; use `PROD_ONLY` tag for production-only requirements.
- Separate topics of concern into distinct files when a file has grown too
  broad.
- Update `specs/README.md` to reflect all file additions, removals, renames,
  and topic reorganizations.

### Phase 5 — Update Design Notes (`notes/`)

- Promote insights, tradeoffs, and lessons from `IMPLEMENTATION_NOTES.md`
  into the appropriate `notes/*.md` file. Do not duplicate spec text.
- Mark unresolved items explicitly: `Open Question:` / `Design Decision:`.
- Update `notes/README.md` when files are added, removed, or reorganized.
- Every `notes/*.md` (except `notes/README.md`) must have valid YAML
  frontmatter with at least `title` and `status`.

### Phase 6 — Update Agent Guidance (`AGENTS.md`)

Promote recurring implementation patterns and conventions from
`IMPLEMENTATION_NOTES.md` into `AGENTS.md`. Keep entries precise, actionable,
and minimal.

### Phase 7 — Tidy Ephemeral Sources

For items in `IMPLEMENTATION_NOTES.md` now fully captured in `specs/`,
`notes/`, or `AGENTS.md`, apply line-level strikethrough with a reference:

```markdown
~~Original note text~~
→ captured in notes/foo.md
```

Do **not** delete the original text. Do **not** reference `IMPLEMENTATION_NOTES.md`
from durable docs.

### Phase 8 — Lint and Commit

1. Invoke the `format-markdown` skill on all new/modified markdown files.
   Fix all errors.
2. If a requirement conflict cannot be resolved, add a note to
   `plan/IMPLEMENTATION_NOTES.md` and **stop before committing**.
3. Invoke the `commit` skill. Use multiple commits for thematically distinct
   changes (e.g., spec refinements, notes promoted, AGENTS.md updates).

## Constraints

- Do not modify code or tests.
- Do not process `plan/IDEAS.md` — that is `ingest-idea`'s domain.
- Do not skip the grill-me phase — it must complete before any writing.
- Do not reference `IMPLEMENTATION_NOTES.md` from durable docs.
- Verify assumptions against the codebase; do not assert absence without
  evidence.
