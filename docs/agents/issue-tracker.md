---
stakeholder_type: [project-contributor]
---

# Issue tracker: GitHub

To fetch an issue, run `gh issue view <number> --comments`.
A bare `#N` may be a pull request, so try `gh pr view N` first and fall back to `gh issue view N`.

The full rules for the GitHub issue tracker are in `notes/parallel-development.md` § "GitHub Issue Tracker".
Never create an issue with `gh issue create`: it cannot set the issue type or the parent and blocker links.

Epics, label taxonomy, and triage labels are covered there and in `notes/epic-themes.md` § "Triage Labels".
