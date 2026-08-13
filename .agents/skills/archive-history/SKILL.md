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
embedded in the entry body. History entries become immutable once merged into
`main` — see [Constraints](#constraints).

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
HISTORY_OUTPUT=$(cat <<'ENDOFENTRY' | PYTHONPATH= uv run append-history <TYPE> \
    --title "<TITLE>" \
    --source "<SOURCE>"

<Full entry body — include PR URL, impl issue links, and outcome summary>

ENDOFENTRY
)
```

Capture the output in `HISTORY_OUTPUT`. The tool either:

- **File mode**: writes `plan/history/YYMM/<type>/<source>.md`, regenerates
  the local `plan/history/YYMM/README.md` (gitignored), and prints the file
  path to stdout.
- **GitHub comment mode** (`implementation`/`idea` with `--source ISSUE-N`):
  posts a comment on the issue and prints the comment URL to stdout
  (starts with `https://`). No file is written.

### Step 2 — Check output mode

```bash
if [[ "$HISTORY_OUTPUT" == https://* ]]; then
    echo "Posted as GitHub comment: $HISTORY_OUTPUT"
    # Skip Steps 3–5 (no file was written).
    exit 0
fi
```

If the output is a URL, the entry was posted as a GitHub comment — skip
all `git` steps (HM-08-004). Record the URL for the caller's reference.

### Step 3 — Lint the new history files

Only reached when a file was written:

```bash
markdownlint-cli2 --fix --config .markdownlint-cli2.yaml \
  "plan/history/$(date +%y%m)/**/*.md"
```

### Step 4 — Stage and commit

```bash
git add plan/history/
git commit -m "history: archive <TYPE> <SOURCE> — <TITLE>

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

The `Co-authored-by` trailer is **required** on this commit just as on all
others — the history commit is the most commonly missing it.

### Step 5 — Push

```bash
git push "https://x-access-token:$(gh auth token)@github.com/CERTCC/Vultron.git" HEAD
```

---

## Constraints

- **Always call after PR creation** — include the PR URL in the entry body.
- **One entry per invocation** — for multiple entries, call this skill in a loop.
- **Skip git steps when output is a URL** — GitHub comment mode writes no file;
  `git add`, commit, and push are not needed (HM-08-004, HM-08-006).
- **Do not call `git push` separately** — this skill always pushes as its final step (file mode only).
- **Do not amend** — open a new commit via a fresh invocation rather than amending.
- History files are **immutable once merged into main** — not once pushed. While the
  entry is still on an unmerged branch it is ordinary working-branch content: if a
  fact in it goes stale before the PR merges (a reparented epic, a renumbered
  issue), correct it in place and commit the fix. Immutability starts at merge,
  because that is when the entry becomes shared history others may cite. After the
  merge, correct the record with a **new** entry rather than editing the old one.
