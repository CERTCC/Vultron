---
source: CONCERN-507
timestamp: '2026-05-19T20:18:39.672591+00:00'
title: AGENTS.md routing policy and per-directory structure
type: learning
---

## #507 Planning and specification files change so frequently that agent guidance goes stale quickly

`plan/` and guidance docs (`AGENTS.md`, `specs/README.md`) are among the highest-churn
files in the repository (386, 306, and 87+ changes respectively in the last 90 days).
Agents and contributors working from cached or slightly-stale copies may apply
outdated rules.

**Root cause**: AGENTS.md is a monolith with no routing policy — pitfalls and
conventions that belong in per-directory AGENTS.md files or notes/ accumulate at root,
driving high churn and stale agent context. plan/ churn is by design (ephemeral files),
but AGENTS.md and specs/README.md staleness is a structural problem.

**Resolution**: 2026-05-19 — added routing policy note `notes/agents-md-structure.md`
(PR #575) and AGENTS.md Common Pitfalls entry for routing awareness.
Implementation tracked in #576 (per-directory AGENTS.md stubs + content migration).
Docs PR: <https://github.com/CERTCC/Vultron/pull/575>5>.
