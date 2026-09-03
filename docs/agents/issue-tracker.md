# Issue tracker: GitHub

Issues and PRDs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: **never `gh issue create`** — it cannot set issue types, parent/child relationships, or blocker/blocked-by links. Use `.agents/skills/manage-github-issue/manage_github_issue.sh` or the `createIssue` GraphQL mutation directly. Type IDs and relationship mutations: `.agents/skills/manage-github-issue/REFERENCE.md`.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v` — `gh` does this automatically when run inside a clone.

## Epics

Epics are the `Epic` issue type, **not** a label. An Epic is a first-class GitHub issue whose `issueType` is `Epic`, with its member issues wired as sub-issues via GraphQL (the `addSubIssue` mutation). There is no "epic" label — do not create or search for one. Detect Epics by `issueType.name == "Epic"` and find their contents through the sub-issue relationship, not a label query. Create them with the `create-epic` skill.

## Backtick-safe bodies

**Never pass backtick-containing markdown in a double-quoted `--body`.** Use a single-quoted heredoc:

```bash
gh issue comment <N> --repo CERTCC/Vultron --body "$(cat <<'EOF'
Use `code` freely here.
EOF
)"
```

The same rule applies to `gh issue edit --body`, `gh pr create --body`, etc.

## Pull requests as a triage surface

**PRs as a request surface: no.**

When set to `yes`, PRs run through the same labels and states as issues, using the `gh pr` equivalents:

- **Read a PR**: `gh pr view <number> --comments` and `gh pr diff <number>` for the diff.
- **List external PRs for triage**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments` then keep only `authorAssociation` of `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, or `NONE` (drop `OWNER`/`MEMBER`/`COLLABORATOR`).
- **Comment / label / close**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub shares one number space across issues and PRs, so a bare `#42` may be either — resolve with `gh pr view 42` and fall back to `gh issue view 42`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.
