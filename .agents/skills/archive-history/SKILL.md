---
name: archive-history
description: >
  Archive a single completed work item to plan/history/ using the append-history
  tool, then lint, stage, commit, and push the resulting files. Always call this
  skill AFTER a PR has been created (so the PR URL can be included in the entry
  body). Caller constructs the entry body and passes it as a heredoc. Handles
  one entry at a time; callers that need to archive multiple items (e.g., learn)
  invoke this skill once per item in a loop. Use whenever any other skill calls
  `uv run append-history`.
---

# Skill: Archive History

Archive one completed work item to `plan/history/`, lint the new files, and
commit + push them to the current branch.

**Always invoke this skill AFTER the PR is opened** — so the PR URL can be
embedded in the entry body. Since history entries are immutable once committed,
completeness matters.

---

## Interface

The caller provides four pieces of information:

| Parameter | Description | Example |
|---|---|---|
| `TYPE` | Entry type passed to `append-history` | `idea`, `implementation`, `learning`, `priority` |
| `TITLE` | Short human-readable summary | `AGENTS.md routing policy` |
| `SOURCE` | Originating identifier | `CONCERN-507`, `IDEA-42`, `ISSUE-576` |
| Body | Full entry text piped via heredoc | See caller templates below |

---

## Procedure

### Step 1 — Pipe entry body to `append-history`

```bash
cat <<'ENDOFENTRY' | uv run append-history <TYPE> \
    --title "<TITLE>" \
    --source "<SOURCE>"

<Full entry body — include PR URL, impl issue links, and outcome summary>

ENDOFENTRY
```

The tool writes `plan/history/YYMM/<type>/<source>.md` and regenerates
`plan/history/YYMM/README.md` locally (the README is gitignored).

### Step 2 — Lint the new history files

```bash
markdownlint-cli2 --fix --config .markdownlint-cli2.yaml \
  "plan/history/$(date +%y%m)/**/*.md"
```

Fix any lint errors in the generated files before continuing.

### Step 3 — Stage history files

```bash
git add plan/history/
```

### Step 4 — Commit

```bash
uv run git commit -m "history: archive <TYPE> <SOURCE> — <TITLE>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

### Step 5 — Push

```bash
git push "https://x-access-token:$(gh auth token)@github.com/CERTCC/Vultron.git" HEAD
```

---

## Caller templates

Each caller skill should replace its inline `uv run append-history` +
`git add plan/history/` + `git commit` sequence with an invocation of
this skill. The caller is responsible for constructing the entry body;
this skill owns the tool invocation, lint, stage, commit, and push.

### plan-issue (Idea)

```text
TYPE    = idea
TITLE   = <short idea title>
SOURCE  = IDEA-<ISSUE_NUMBER>
BODY    = Full original idea text + "**Processed**: YYYY-MM-DD — ..." line
          + "Docs PR: <PR_URL>."
```

### plan-issue (Concern)

```text
TYPE    = learning
TITLE   = <short concern title>
SOURCE  = CONCERN-<ISSUE_NUMBER>
BODY    = Full original concern body + "**Resolved**: YYYY-MM-DD — ..."
          + "Docs PR: <PR_URL>. Implementation tracked in #<IMPL_ISSUE>."
```

### learn (incoming learning file)

```bash
# After adding the promotion note to the file body, run:
uv run append-history --from-file plan/incoming/learnings/<YYYYMMDD-SLUG>.md
```

This moves the file to `plan/history/YYMM/learning/` and deletes the source.

### build

```text
TYPE    = implementation
TITLE   = <short task title>
SOURCE  = ISSUE-<N>   (or full GitHub URL)
BODY    = "## Issue #<N> — <title>\n\n<completion summary, PR link>"
```

### update-priorities

```text
TYPE    = priority
TITLE   = <priority group title>
SOURCE  = PRIORITY-<number>
BODY    = <priority summary and completion notes>
```

---

## Constraints

- **Always call after PR creation** — the entry body should include the PR URL.
- **One entry per invocation** — for multiple entries, call this skill in a loop.
- **Do not call `git push` separately** — this skill always pushes as its final
  step.
- **Do not amend** — if the commit already exists, open a new commit via a fresh
  invocation rather than amending.
- History files are **immutable** once pushed — do not edit them after this
  skill completes.
