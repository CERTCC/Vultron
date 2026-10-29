---
stakeholder_type: [project-contributor]
---

# Issue tracker: GitHub

To fetch an issue, run `gh issue view <number> --comments`.
A bare `#N` may be a pull request, so try `gh pr view N` first and fall back to `gh issue view N`.

The full rules for the GitHub issue tracker are in `notes/parallel-development.md` § "GitHub Issue Tracker".
Create every issue through the `create-issue` skill, never with `gh issue create`: that command cannot set the issue type or the parent and blocker links.
The skill's script refuses an issue without one `theme:` label, a `Theme:` line, and a parent with the same theme.

Epics, label taxonomy, and triage labels are covered there and in `notes/epic-themes.md` § "Triage Labels".
