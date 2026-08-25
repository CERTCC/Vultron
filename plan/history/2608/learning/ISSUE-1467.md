---
title: .agents/skills/ and .claude/skills/ are linked — edits and git staging must use .agents/ path
type: learning
timestamp: '2026-08-21T00:00:00+00:00'
source: ISSUE-1467
signal: tooling-issue
---

`.claude/skills/` is a symlink to `.agents/skills/`. Within that directory,
individual `SKILL.md` files share the same inode (hard links). Two consequences:

**Editing**: Editing `.agents/skills/<name>/SKILL.md` with the Edit tool
modifies both copies on disk. When both need the same change, edit only the
`.agents/` path — editing both duplicates the change.

**Git staging**: `git add .claude/skills/<name>/SKILL.md` fails with
`fatal: beyond a symbolic link` because the path traverses a symlink directory.
Always stage through the real path: `git add .agents/skills/<name>/SKILL.md`.

Confirmed: `ls -la` showing same inode; `git add .claude/...` error reproduced
in ISSUE-2466 session (2026-08-24).

**Promoted**: 2026-08-24 — captured in AGENTS.md.
Docs PR: [PR URL TBD].
