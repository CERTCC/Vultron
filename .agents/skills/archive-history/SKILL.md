---
name: archive-history
description: >
  Archive a single completed work item to plan/history/ using the append-history
  tool, then stage, commit, and push the resulting files. Always call this
  skill AFTER a PR has been created (so the PR URL can be included in the entry
  body). Caller constructs the entry body and passes it as a heredoc. Handles
  one entry at a time; callers that need to archive multiple items (e.g., learn)
  invoke this skill once per item in a loop. Use whenever any other skill calls
  `uv run append-history`.
---

# Skill: Archive History

Archive one completed work item to `plan/history/` and commit + push it to the
current branch.
History entries are not markdown-linted: the root `.markdownlint-cli2.yaml`
ignores `**/plan/history/**`, so `--fix` can never rewrite one (HM-01-005, #2952).

**Always invoke this skill AFTER the PR is opened** — so the PR URL can be
embedded in the entry body. History entries become immutable once merged into
`main` — see [Constraints](#constraints).

---

## Interface

The caller provides four pieces of information (see the calling skill for body format):

| Parameter | Description | Example |
|---|---|---|
| `TYPE` | Entry type | `idea`, `implementation`, `learning`, `note`, `priority` |
| `TITLE` | Short summary | `AGENTS.md routing policy` |
| `SOURCE` | Originating identifier | `ISSUE-576` (implementation, idea), `IDEA-26042702` (idea), `CONCERN-507` (learning) |
| Body | Full entry text via heredoc | Include PR URL and outcome summary |

---

The `note` type is used when archiving a stale section (card) from a `notes/*.md`
file. Source ID convention: `NOTES-<file-stem>--<section-slug>` (e.g.,
`NOTES-bt-pitfalls--bt-failure-reason-propagation`). Entry body format: archiving
reason + superseding pointer + `---` + original section content verbatim.
See the `learn` and `decision-audit` skills for when to invoke this type.

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
  posts a comment on issue N and prints the comment URL to stdout (starts with
  `https://`). No file is written. N must be an existing CERTCC/Vultron issue,
  not a pull request, and `gh` must be authenticated; otherwise the tool exits 1
  and writes nothing.

`implementation` and `idea` take only these sources: `ISSUE-N` (comment),
`ISSUE-N-<slug>` (an `implementation` file) and `IDEA-YYMMDDNN` (an `idea`
file). Any other source, such as `TASK-4646` or `CONCERN-507`, is refused with
the accepted forms named (HM-08-008). `learning`, `note` and `priority` sources
are free-form.

### Step 2 — Check output mode

```bash
if [[ "$HISTORY_OUTPUT" == https://* ]]; then
    echo "Posted as GitHub comment: $HISTORY_OUTPUT"
    # Skip Steps 3–4 (no file was written).
    exit 0
fi
```

If the output is a URL, the entry was posted as a GitHub comment — skip
all `git` steps (HM-08-004). Record the URL for the caller's reference.

### Step 3 — Stage and commit

```bash
git add plan/history/
git commit -m "history: archive <TYPE> <SOURCE> — <TITLE>"
```

### Step 4 — Push

```bash
git push -u origin HEAD
```

---

## Constraints

- **Always call after PR creation** — include the PR URL in the entry body.
- **One entry per invocation** — for multiple entries, call this skill in a loop.
- **Skip git steps when output is a URL** — GitHub comment mode writes no file;
  `git add`, commit, and push are not needed (HM-08-004, HM-08-006).
- **Do not call `git push` separately** — this skill always pushes as its final step
  (file mode only).
- **Do not amend** — open a new commit via a fresh invocation rather than amending.
- History files are **immutable once merged into main** — not once pushed. While the
  entry is still on an unmerged branch it is ordinary working-branch content: if a
  fact in it goes stale before the PR merges (a reparented epic, a renumbered
  issue), correct it in place and commit the fix. Immutability starts at merge,
  because that is when the entry becomes shared history others may cite. After the
  merge, correct the record with a **new** entry rather than editing the old one.
