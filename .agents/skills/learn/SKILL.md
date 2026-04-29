---
name: learn
description: >
  Promote lessons learned from the build process into durable specifications
  and design notes. Reads BUILD_LEARNINGS.md (internal source), analyzes
  gaps, interviews the user with grill-me to align on scope, then writes to
  specs/, notes/, and AGENTS.md before committing. Use when build execution
  has produced insights that should be reflected in specs or notes. For
  external ideas (IDEAS.md), use ingest-idea instead.
---

# Skill: Learn

Integrate lessons learned from build execution into the project's durable
specification and design documentation. The input is what the build process
has discovered (`BUILD_LEARNINGS.md`); the
output is refined `specs/`, `notes/`, and `AGENTS.md`.

**Constraint**: Modify **documentation files only**, including Markdown files
and YAML spec files in `specs/`. Do not modify code or tests.

**Trigger**: Use this skill when `plan/BUILD_LEARNINGS.md` has unprocessed
entries that should be promoted into durable docs.

> For new external ideas from `plan/IDEAS.md`, use `ingest-idea` instead.

## Quick Start

1. Read `plan/BUILD_LEARNINGS.md`.
2. Invoke `study-project-docs` for full context (specs, notes, code).
3. Analyze what the build process has learned vs. what specs and notes capture.
4. Invoke `grill-me` to align on scope and decisions — before writing anything.
5. Write to `specs/`, `notes/`, and `AGENTS.md`.
6. Archive each processed entry via `uv run append-history learning`, then
   delete it from `plan/BUILD_LEARNINGS.md`.
7. Invoke `format-markdown`, then `commit`.

## Workflow

### Phase 1 — Load Internal Sources and Context

1. Read `plan/BUILD_LEARNINGS.md` — open questions, observations, and
   constraints from recent build/bugfix runs (ephemeral queue; entries are
   deleted after archiving).
2. Invoke the `study-project-docs` skill for full context: specs JSON,
   plan files, docs/adr/, notes/, AGENTS.md, and a code scan.

> `BUILD_LEARNINGS.md` is an ephemeral queue. Entries are deleted after
> archiving. Any critical insight in an entry **must be promoted** to
> `specs/` or `notes/` before being archived.

### Phase 2 — Analyze Gaps

Identify what the build process has learned that is not yet captured in
durable docs:

1. Missing requirements — behavior exists in code but has no spec.
2. Ambiguous or untestable requirements — reality diverges from what's written.
3. Redundant or contradictory requirements across spec files.
4. Agent guidance patterns that keep recurring in `BUILD_LEARNINGS.md`
   but are not yet in `AGENTS.md`.
5. Recent completed-task insights — when needed, read relevant monthly index
   files in `plan/history/` (e.g., `plan/history/YYMM/README.md`) to identify
   which history entries contain architectural lessons, then open those files.

### Phase 3 — Interview with Grill-Me

Invoke the `grill-me` skill. Resolve one question at a time (using `ask_user`)
with a recommended answer before writing anything:

- Which insights from `BUILD_LEARNINGS.md` are most important to promote?
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

- Promote insights, tradeoffs, and lessons from `BUILD_LEARNINGS.md`
  into the appropriate `notes/*.md` file. Do not duplicate spec text.
- Mark unresolved items explicitly: `Open Question:` / `Design Decision:`.
- Update `notes/README.md` when files are added, removed, or reorganized.
- Every `notes/*.md` (except `notes/README.md`) must have valid YAML
  frontmatter with at least `title` and `status`.

### Phase 6 — Update Agent Guidance (`AGENTS.md`)

Promote recurring implementation patterns and conventions from
`BUILD_LEARNINGS.md` into `AGENTS.md`. Keep entries precise, actionable,
and minimal.

### Phase 7 — Archive and Delete Processed Entries

For each entry in `plan/BUILD_LEARNINGS.md` that has been fully promoted to
`specs/`, `notes/`, or `AGENTS.md`:

1. Archive the entry via `uv run append-history learning`:

   ```bash
   cat <<'EOF' | uv run append-history learning
   ---
   title: <short observation title>
   type: learning
   date: <YYYY-MM-DD>
   source: <label from the entry header, e.g. LABEL>
   ---

   <full original entry text here>

   **Promoted**: YYYY-MM-DD — captured in <destination file(s)>.
   EOF
   ```

2. Delete the entry from `plan/BUILD_LEARNINGS.md` entirely — no
   strike-through, no tombstone.

Do **not** reference `plan/BUILD_LEARNINGS.md` from durable docs.

### Phase 8 — Lint and Commit

1. Invoke the `format-markdown` skill on all new/modified markdown files.
   Fix all errors.
2. If a requirement conflict cannot be resolved, add a note to
   `plan/BUILD_LEARNINGS.md` and **stop before committing**.
3. Invoke the `commit` skill. Use multiple commits for thematically distinct
   changes (e.g., spec refinements, notes promoted, AGENTS.md updates).

## Constraints

- Do not modify code or tests.
- Do not process `plan/IDEAS.md` — that is `ingest-idea`'s domain.
- Do not skip the grill-me phase — it must complete before any writing.
- Do not reference `plan/BUILD_LEARNINGS.md` from durable docs.
- Archive processed entries via `uv run append-history learning`; do not
  leave them in the file after promoting.
- Verify assumptions against the codebase; do not assert absence without
  evidence.
