---
title: .agents/skills/ and .claude/skills/ are hard-linked — edits to either affect both
type: learning
timestamp: '2026-08-21T00:00:00+00:00'
source: ISSUE-1467
signal: tooling-issue
---

`.agents/skills/<name>/SKILL.md` and `.claude/skills/<name>/SKILL.md` share the
same inode (hard links). Editing one with the Edit tool modifies both on disk.

When both copies need the same change (which is the common case), edit only
`.agents/skills/<name>/SKILL.md` — the `.claude/skills/` copy updates
automatically. Editing both in sequence duplicates the change, causing double
sections.

Confirmed by: `ls -la` showing identical size + timestamp, and `diff` showing
no differences before and after separate edits.

**Promoted**: 2026-08-24 — captured in AGENTS.md.
Docs PR: [PR URL TBD].
