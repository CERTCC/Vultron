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
embedded in the entry body. History entries are immutable once committed.

---

## Interface

The caller provides four pieces of information (see the calling skill for body format):

| Parameter | Description | Example |
|---|---|---|
| `TYPE` | Entry type | `idea`, `implementation`, `learning`, `priority` |
| `TITLE` | Short summary | `AGENTS.md routing policy` |
| `SOURCE` | Originating identifier | `CONCERN-507`, `IDEA-42`, `ISSUE-576` |
| Body | Full entry text via heredoc | Include PR URL and outcome summary |

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

### Step 3 — Stage and commit

```bash
git add plan/history/
uv run git commit -m "history: archive <TYPE> <SOURCE> — <TITLE>"
```

### Step 4 — Push

```bash
git push "https://x-access-token:$(gh auth token)@github.com/CERTCC/Vultron.git" HEAD
```

---

## Constraints

- **Always call after PR creation** — include the PR URL in the entry body.
- **One entry per invocation** — for multiple entries, call this skill in a loop.
- **Do not call `git push` separately** — this skill always pushes as its final step.
- **Do not amend** — open a new commit via a fresh invocation rather than amending.
- History files are **immutable** once pushed.
