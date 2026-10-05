---
source: NOTES-history-management--github-comment-output-mode
timestamp: '2026-10-02T16:21:29.862785+00:00'
title: GitHub Comment Output Mode (source rules, skill behaviour, comment format)
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered + redundant — HM-08-001..006 state the mode and it is built (_post_github_comment, archive-history skips git steps on a URL). The Backfill subsection stays active.
**Superseded by:** HM-08-001..006; vultron/metadata/history/cli.py

---

## GitHub Comment Output Mode

For `implementation` and `idea` entry types, when `--source` resolves to a GitHub
issue number (`ISSUE-N` or bare integer N), `append-history` posts the entry body
as a comment on that issue rather than writing a file. This co-locates the
completion narrative with the original problem statement.

### Source resolution rules

| `--source` value | Output |
|---|---|
| `ISSUE-2153` | Comment on issue #2153 |
| `2153` (bare integer) | Comment on issue #2153 |
| `IDEA-26042702` | File at `plan/history/YYMM/idea/IDEA-26042702.md` |
| `TASK-BTND5` | File at `plan/history/YYMM/implementation/TASK-BTND5.md` |

`learning` and `priority` types always write files regardless of source format.

### Skill behaviour change

When `append-history` posts a GitHub comment it prints the comment URL to stdout
(not a file path). The `archive-history` skill MUST detect this and skip the
`git add plan/history/` and commit/push steps — there is no new file to stage.

### Comment format

```markdown
**History: implementation — Fix demo config cache leak**

<full entry body text>
```

The heading line uses the entry type and `--title` value. The body follows
unchanged from what would have been the file-based Markdown body.
