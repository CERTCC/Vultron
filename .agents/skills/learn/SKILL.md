---
name: learn
description: >
  Promote lessons learned from the build process into durable specifications
  and design notes. First refreshes docs/reference/codebase/ via
  acquire-codebase-knowledge, then reads BUILD_LEARNINGS.md and queries
  GitHub for open type:Concern issues (both as input queues), analyzes
  gaps, interviews the user with grill-me to align on scope, then writes
  to specs/, notes/, and AGENTS.md, opens a docs-only PR with the
  specs-notes label, and archives processed entries. Use when build
  execution has produced insights that should be reflected in specs or
  notes. For external ideas (GitHub Idea-type issues), use ingest-idea
  instead.
---

# Skill: Learn

Integrate lessons learned from build execution into the project's durable
specification and design documentation. The inputs are what the build process
has discovered (`BUILD_LEARNINGS.md`) and open GitHub `type:Concern` issues
tracked in the repository; the output is refined `specs/`, `notes/`, and
`AGENTS.md`.

**Constraint**: Modify **documentation files only**, including Markdown files
and YAML spec files in `specs/`. Do not modify code or tests.

**Trigger**: Use this skill when `plan/BUILD_LEARNINGS.md` has unprocessed
entries that should be promoted into durable docs.

> For new external ideas (GitHub Idea-type issues), use `ingest-idea` instead.

## Quick Start

1. **Freshen** the worktree slot (before any writes): `manage_worktree.sh freshen`
2. Invoke `acquire-codebase-knowledge` — full scan, refreshes all 7 docs
   in `docs/reference/codebase/`.
3. Read `plan/BUILD_LEARNINGS.md` and query GitHub for open `type:Concern`
   issues (both are input queues).
4. Invoke `study-project-docs` for full context (specs, notes, code) — it
   now reads the freshly updated codebase docs.
5. Analyze what the build process has learned vs. what specs and notes capture.
6. Invoke `grill-me` to align on scope and decisions — before writing anything.
   Include GitHub Concern issue triage in this phase (no separate triage step
   needed).
7. **Create the task branch**: `git switch -c learn/<YYYYMMDD>-<slug>`
   (worktree was already freshened in step 1; branch here after slug is known)
8. Write to `specs/`, `notes/`, and `AGENTS.md`.
9. Archive each processed BUILD_LEARNINGS entry and each resolved Concern issue
   via `uv run append-history learning`; delete BUILD_LEARNINGS entries from
   their source file and close each resolved GitHub Concern issue with a
   resolution comment.
10. Invoke `format-markdown`.
11. Commit (including updated `docs/reference/codebase/` files), push, and
    open a docs-only PR with `specs-notes` label.

## Workflow

### Phase 0 — Freshen and Refresh Codebase Knowledge

**First, freshen the worktree slot** (if running in a `wt/*` slot) so
all subsequent writes land on a clean, up-to-date baseline:

```bash
FRESHEN="$HOME/.copilot/skills/manage-worktree/scripts/manage_worktree.sh"
[ -f "$FRESHEN" ] && bash "$FRESHEN" freshen
```text

Do this **before** `acquire-codebase-knowledge` runs — the scan regenerates
files in `docs/reference/codebase/` (uncommitted), and those outputs must not
be clobbered by a later `git reset --hard`.

Then invoke the `acquire-codebase-knowledge` skill (full scan, no focus area
restriction). This regenerates all seven files in `docs/reference/codebase/`
from the current state of the repository before any gap analysis begins,
ensuring `study-project-docs` in Phase 1 reads an accurate baseline.

Always run this phase unconditionally — `learn` runs infrequently enough
that the cost of a full scan is justified on every invocation.

### Phase 1 — Load Internal Sources and Context

1. Read `plan/BUILD_LEARNINGS.md` — open questions, observations, and
   constraints from recent build/bugfix runs (ephemeral queue; entries are
   deleted after archiving).
2. Query GitHub for all open `type:Concern` issues — these are the tracked
   technical concerns, risks, and debt items surfaced by prior codebase scans
   and the `process-concerns` skill (second input queue; resolved issues are
   archived and closed):

   ```bash
   gh issue list \
     --repo CERTCC/Vultron \
     --state open \
     --label concern \
     --json number,title,body
   ```text

1. Invoke the `study-project-docs` skill for full context: specs JSON,
   plan files, docs/adr/, notes/, AGENTS.md, and a code scan. Because
   Phase 0 has already refreshed the codebase docs, `study-project-docs`
   will read up-to-date architecture and structure information.

> `BUILD_LEARNINGS.md` is an ephemeral queue. Entries are deleted after
> archiving. Any critical insight in an entry **must be promoted** to
> `specs/` or `notes/` before being archived.

### Phase 2 — Analyze Gaps

Identify what the build process and codebase scan have surfaced that is not
yet captured in durable docs. Consider both BUILD_LEARNINGS entries and
open GitHub Concern issues:

1. Missing requirements — behavior exists in code but has no spec.
2. Ambiguous or untestable requirements — reality diverges from what's written.
3. Redundant or contradictory requirements across spec files.
4. Agent guidance patterns that keep recurring in `BUILD_LEARNINGS.md`
   but are not yet in `AGENTS.md`.
5. Open GitHub `type:Concern` issues that reveal missing spec requirements or
   durable design notes.
6. Recent completed-task insights — when needed, read relevant monthly index
   files in `plan/history/` (e.g., `plan/history/YYMM/README.md`) to identify
   which history entries contain architectural lessons, then open those files.

### Phase 3 — Interview with Grill-Me

Invoke the `grill-me` skill. Resolve one question at a time (using `ask_user`)
with a recommended answer before writing anything:

- Which insights from `BUILD_LEARNINGS.md` are most important to promote?
- Which open GitHub `type:Concern` issues are addressed by this session's
  insights, outdated, or should be promoted to specs/notes? (Resolved
  concerns go to `specs/` if they reveal missing requirements, `notes/`
  otherwise.)
- Which gaps are most critical to close in this run?
- Are there unresolvable conflicts that need a human decision?
- Does any spec change require code verification first?

Answer questions from codebase exploration where possible.

**After grill-me completes — create the task branch before writing any files:**

```bash
git switch -c learn/<YYYYMMDD>-<slug>
```text

The worktree was already freshened in Phase 0. All file writes (Phases 4–7)
happen on this branch so they are never at risk from a `git reset --hard`.

### Phase 4 — Refine Specifications (`specs/`)

- Clarify, split, merge, or remove requirements; keep each atomic, specific,
  concise, and verifiable.
- `specs/` are for *what*, not *how*.
- Eliminate redundancy; use `PROD_ONLY` tag for production-only requirements.
- Separate topics of concern into distinct files when a file has grown too
  broad.
- Update `specs/README.md` to reflect all file additions, removals, renames,
  and topic reorganizations.

**ADR decision (MS-11):** When adding new spec entries, apply the decision-tree
heuristic in `notes/specs-vs-adrs.md` to decide whether the underlying design
choice also warrants a new ADR. Write an ADR when a meaningful alternative was
evaluated and rejected; skip it for uncontested rules (MS-11-002, MS-11-005).
When both are created, cross-reference them: cite the ADR in the spec's
`rationale` field, and list the generated spec IDs in the ADR's "More
Information" section (MS-11-004).

### Phase 5 — Update Design Notes (`notes/`)

- Promote insights, tradeoffs, and lessons from `BUILD_LEARNINGS.md` and
  resolved GitHub Concern issues into the appropriate `notes/*.md` file.
  Do not duplicate spec text.
- Mark unresolved items explicitly: `Open Question:` / `Design Decision:`.
- Update `notes/README.md` when files are added, removed, or reorganized.
- Every `notes/*.md` (except `notes/README.md`) must have valid YAML
  frontmatter with at least `title` and `status`.

### Phase 6 — Update Agent Guidance (`AGENTS.md`)

Promote recurring implementation patterns and conventions from
`BUILD_LEARNINGS.md` into `AGENTS.md`. Keep entries precise, actionable,
and minimal.

### Phase 7 — Prepare Archive Content and Close Processed Entries

For each BUILD_LEARNINGS entry and each resolved GitHub Concern issue that
has been fully promoted to `specs/`, `notes/`, or `AGENTS.md`:

1. Draft the archive body for each item (store in memory — the actual
   `archive-history` invocations happen in Phase 9 after the PR URL is known):

   ```text

   TYPE    = learning
   TITLE   = <short observation title>
   SOURCE  = <label from the entry header, e.g. LABEL>
   BODY    = <full original BUILD_LEARNINGS entry or Concern body>
             + "**Promoted**: YYYY-MM-DD — captured in <destination file(s)>."
             + "Docs PR: <PR_URL>."  ← filled in after PR is opened

   ```text

2. **For BUILD_LEARNINGS entries**: delete the entry from
   `plan/BUILD_LEARNINGS.md` entirely — no strike-through, no tombstone.

3. **For resolved GitHub Concern issues**: close the issue and add a
   resolution comment after the PR is open (step in Phase 9):

   ```bash
   gh issue comment "${ISSUE_NUMBER}" --repo CERTCC/Vultron \
     --body "✅ Resolved.

   - Docs PR: <PR_URL>
   - Promoted to: \`specs/<topic>.yaml\` and/or \`notes/<topic>.md\`

   Design decisions are now captured in durable documentation."

   gh issue close "${ISSUE_NUMBER}" --repo CERTCC/Vultron
   ```text

Do **not** reference `plan/BUILD_LEARNINGS.md` from durable docs.

### Phase 8 — Lint, Commit, and Open PR

1. Invoke the `format-markdown` skill on all new/modified markdown files.
   Fix all errors.
2. If a requirement conflict cannot be resolved, add a note to
   `plan/BUILD_LEARNINGS.md` and **stop before committing**.
3. Stage, commit, push, and open a docs-only PR (branch was created at the
   end of Phase 3):

   ```bash
   git add specs/<changed-files> notes/<changed-files> AGENTS.md \
       plan/BUILD_LEARNINGS.md docs/reference/codebase/
   git commit -m "docs: promote BUILD_LEARNINGS — <topic>

   - <bullet: what was promoted and where>
   - Archive <N> entr[y/ies] via archive-history (after PR)
   - Close <N> resolved GitHub Concern issue(s) with resolution comments
   - Refresh docs/reference/codebase/ via acquire-codebase-knowledge

   Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
   git push -u origin learn/<YYYYMMDD>-<slug>

   gh pr create --repo CERTCC/Vultron \
     --title "docs: promote BUILD_LEARNINGS — <topic>" \
     --body "Docs-only PR: promotes build learnings to specs/, notes/,
   and/or AGENTS.md. Includes refreshed docs/reference/codebase/ output.

   No .py files changed." \
     --label "specs-notes"
   ```text

   Use multiple commits for thematically distinct changes (e.g., spec
   refinements, notes promoted, AGENTS.md updates). This PR carries the
   `specs-notes` label for reviewer awareness.

### Phase 9 — Archive Entries and Close Issues

Now that the PR URL is known, archive each item by invoking the
`archive-history` skill once per entry. For each item, pass:

```text
TYPE    = learning
TITLE   = <short observation title>
SOURCE  = <label from the BUILD_LEARNINGS header>
BODY    = <full original entry text>
          + "**Promoted**: YYYY-MM-DD — captured in <destination file(s)>."
          + "Docs PR: <PR_URL>."
```text

The `archive-history` skill runs `uv run append-history`, lints the new
files, stages `plan/history/`, commits, and pushes — once per entry.

For resolved GitHub Concern issues, post the resolution comment and close
the issue (see Phase 7 step 3 for the comment template).

## Constraints

- Do not modify code or tests.
- Do not process GitHub Idea-type issues — that is `ingest-idea`'s domain.
- Do not skip the grill-me phase — it must complete before any writing.
- Do not reference `plan/BUILD_LEARNINGS.md` from durable docs.
- Archive processed entries via the `archive-history` skill; do not
  call `uv run append-history` directly or leave entries in the file
  after promoting.
- Verify assumptions against the codebase; do not assert absence without
  evidence.
