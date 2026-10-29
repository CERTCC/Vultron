---
name: new-item
description: >
  Retired: use `create-issue`, which absorbed this skill and adds the theme
  and same-theme parent rules. Kept only so old references resolve.
---

# Skill: New Item (Retired)

This skill is retired. Run `create-issue` instead: it does everything `new-item`
did (type inference, duplicate scan, draft-first fields, parent Epic, board
placement) and also picks the one `theme:` label, writes the `Theme:` line,
and routes the issue to an Epic with the same theme.

Do not follow any older copy of this skill's workflow. `manage_github_issue.sh`
now refuses an issue without a theme, a `Theme:` line, and a same-theme parent.
