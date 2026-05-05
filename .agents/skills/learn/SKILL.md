---
name: learn
description: >
  Promote lessons learned from the build process into durable specifications
  and design notes. First refreshes docs/reference/codebase/ via
  acquire-codebase-knowledge, then reads BUILD_LEARNINGS.md and
  CONCERNS.md (both as input queues), analyzes gaps, interviews the user
  with grill-me to align on scope, then writes to specs/, notes/, and
  AGENTS.md, opens a docs-only PR with the specs-notes label, and archives
  processed entries. Use when build execution has produced insights that
  should be reflected in specs or notes. For external ideas (IDEAS.md),
  use ingest-idea instead.
---

# Skill: Learn

Integrate lessons learned from build execution into the project's durable
specification and design documentation. The inputs are what the build process
has discovered (`BUILD_LEARNINGS.md`) and open concerns from the codebase
scan (`docs/reference/codebase/CONCERNS.md`); the output is refined `specs/`,
`notes/`, and `AGENTS.md`.

**Constraint**: Modify **documentation files only**, including Markdown files
and YAML spec files in `specs/`. Do not modify code or tests.

**Trigger**: Use this skill when `plan/BUILD_LEARNINGS.md` has unprocessed
entries that should be promoted into durable docs.

> For new external ideas from `plan/IDEAS.md`, use `ingest-idea` instead.

## Quick Start

1. Invoke `acquire-codebase-knowledge` — full scan, refreshes all 7 docs
   in `docs/reference/codebase/`.
2. Read `plan/BUILD_LEARNINGS.md` and `docs/reference/codebase/CONCERNS.md`
   (both are input queues).
3. Invoke `study-project-docs` for full context (specs, notes, code) — it
   now reads the freshly updated codebase docs.
4. Analyze what the build process has learned vs. what specs and notes capture.
5. Invoke `grill-me` to align on scope and decisions — before writing anything.
   Include CONCERNS.md triage in this phase (no separate triage step needed).
6. Write to `specs/`, `notes/`, and `AGENTS.md`.
7. Archive each processed BUILD_LEARNINGS entry and each resolved CONCERNS
   entry via `uv run append-history learning`, then delete each from its
   source file.
8. Invoke `format-markdown`.
9. Create a branch, commit (including updated `docs/reference/codebase/`
   files), push, and open a docs-only PR with `specs-notes` label.

## Workflow

### Phase 0 — Refresh Codebase Knowledge

Invoke the `acquire-codebase-knowledge` skill (full scan, no focus area
restriction). This regenerates all seven files in `docs/reference/codebase/`
from the current state of the repository before any gap analysis begins,
ensuring `study-project-docs` in Phase 1 reads an accurate baseline.

Always run this phase unconditionally — `learn` runs infrequently enough
that the cost of a full scan is justified on every invocation.

### Phase 1 — Load Internal Sources and Context

1. Read `plan/BUILD_LEARNINGS.md` — open questions, observations, and
   constraints from recent build/bugfix runs (ephemeral queue; entries are
   deleted after archiving).
2. Read `docs/reference/codebase/CONCERNS.md` — open technical concerns,
   risks, and debt items identified by the codebase scan (second input
   queue; resolved entries are archived like BUILD_LEARNINGS entries).
3. Invoke the `study-project-docs` skill for full context: specs JSON,
   plan files, docs/adr/, notes/, AGENTS.md, and a code scan. Because
   Phase 0 has already refreshed the codebase docs, `study-project-docs`
   will read up-to-date architecture and structure information.

> `BUILD_LEARNINGS.md` is an ephemeral queue. Entries are deleted after
> archiving. Any critical insight in an entry **must be promoted** to
> `specs/` or `notes/` before being archived.
>
> `CONCERNS.md` is a **generated** file — `acquire-codebase-knowledge`
> regenerates it on each run. Treat the current snapshot as a read-only
> input: extract any concerns that reveal missing specs or design notes,
> promote them to `specs/` or `notes/`, and record that they are resolved
> in those durable files. Do **not** delete entries from `CONCERNS.md`;
> deletions will not persist across future scans. The durable record of
> resolution lives in `specs/` and `notes/`, not in CONCERNS.md itself.

### Phase 2 — Analyze Gaps

Identify what the build process and codebase scan have surfaced that is not
yet captured in durable docs. Consider both BUILD_LEARNINGS entries and
CONCERNS.md entries:

1. Missing requirements — behavior exists in code but has no spec.
2. Ambiguous or untestable requirements — reality diverges from what's written.
3. Redundant or contradictory requirements across spec files.
4. Agent guidance patterns that keep recurring in `BUILD_LEARNINGS.md`
   but are not yet in `AGENTS.md`.
5. Open concerns in `CONCERNS.md` that reveal missing spec requirements or
   durable design notes.
6. Recent completed-task insights — when needed, read relevant monthly index
   files in `plan/history/` (e.g., `plan/history/YYMM/README.md`) to identify
   which history entries contain architectural lessons, then open those files.

### Phase 3 — Interview with Grill-Me

Invoke the `grill-me` skill. Resolve one question at a time (using `ask_user`)
with a recommended answer before writing anything:

- Which insights from `BUILD_LEARNINGS.md` are most important to promote?
- Which open concerns in `CONCERNS.md` are resolved, outdated, or should be
  promoted to specs/notes? (Resolved concerns go to `specs/` if they reveal
  missing requirements, `notes/` otherwise.)
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

- Promote insights, tradeoffs, and lessons from `BUILD_LEARNINGS.md` and
  resolved `CONCERNS.md` entries into the appropriate `notes/*.md` file.
  Do not duplicate spec text.
- Mark unresolved items explicitly: `Open Question:` / `Design Decision:`.
- Update `notes/README.md` when files are added, removed, or reorganized.
- Every `notes/*.md` (except `notes/README.md`) must have valid YAML
  frontmatter with at least `title` and `status`.

### Phase 6 — Update Agent Guidance (`AGENTS.md`)

Promote recurring implementation patterns and conventions from
`BUILD_LEARNINGS.md` into `AGENTS.md`. Keep entries precise, actionable,
and minimal.

### Phase 7 — Archive and Delete Processed Entries

For each BUILD_LEARNINGS entry and each resolved CONCERNS entry that has been
fully promoted to `specs/`, `notes/`, or `AGENTS.md`:

1. Archive the entry via `uv run append-history learning`:

   ```bash
   cat <<'EOF' | uv run append-history learning \
       --title "<short observation title>" \
       --source "<label from the entry header, e.g. LABEL>"

   <full original entry text here>

   **Promoted**: YYYY-MM-DD — captured in <destination file(s)>.
   EOF
   ```

2. Delete the entry from its source file entirely — no strike-through, no
   tombstone. For BUILD_LEARNINGS entries, delete from
   `plan/BUILD_LEARNINGS.md`. For resolved CONCERNS entries, delete from
   `docs/reference/codebase/CONCERNS.md`.

Do **not** reference `plan/BUILD_LEARNINGS.md` from durable docs.

### Phase 8 — Lint, Commit, and Open PR

1. Invoke the `format-markdown` skill on all new/modified markdown files.
   Fix all errors.
2. If a requirement conflict cannot be resolved, add a note to
   `plan/BUILD_LEARNINGS.md` and **stop before committing**.
3. Create a branch, stage, commit, push, and open a docs-only PR:

   ```bash
   git switch -c learn/<YYYYMMDD>-<slug>
   git add specs/<changed-files> notes/<changed-files> AGENTS.md \
       plan/BUILD_LEARNINGS.md docs/reference/codebase/
   git commit -m "docs: promote BUILD_LEARNINGS — <topic>

   - <bullet: what was promoted and where>
   - Archive <N> entr[y/ies] via append-history learning
   - Refresh docs/reference/codebase/ via acquire-codebase-knowledge

   Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
   git push -u origin learn/<YYYYMMDD>-<slug>

   gh pr create --repo CERTCC/Vultron \
     --title "docs: promote BUILD_LEARNINGS — <topic>" \
     --body "Docs-only PR: promotes build learnings to specs/, notes/,
   and/or AGENTS.md. Includes refreshed docs/reference/codebase/ output.

   No .py files changed." \
     --label "specs-notes"
   ```

   Use multiple commits for thematically distinct changes (e.g., spec
   refinements, notes promoted, AGENTS.md updates). This PR carries the
   `specs-notes` label for reviewer awareness.

## Constraints

- Do not modify code or tests.
- Do not process `plan/IDEAS.md` — that is `ingest-idea`'s domain.
- Do not skip the grill-me phase — it must complete before any writing.
- Do not reference `plan/BUILD_LEARNINGS.md` from durable docs.
- Archive processed entries via `uv run append-history learning`; do not
  leave them in the file after promoting.
- Verify assumptions against the codebase; do not assert absence without
  evidence.
