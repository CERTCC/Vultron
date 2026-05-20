---
source: ISSUE-576
timestamp: '2026-05-20T13:31:59.074121+00:00'
title: AGENTS.md per-directory files + root condensed to 398 lines
type: implementation
---

## Issue #576 — AGENTS.md routing: add per-directory files + migrate root content

Implemented the AGENTS.md routing policy from notes/agents-md-structure.md
(PR #575). Created three new per-directory AGENTS.md files:

- vultron/core/AGENTS.md: handler/use-case naming, use-case protocol,
  add-a-message-type checklist, core key files map, pitfalls
- vultron/wire/as2/AGENTS.md: wire-layer naming, pattern ordering, outbound
  activity factory boundary, AS2 pitfall index
- vultron/adapters/AGENTS.md: FastAPI conventions, adapter key files map,
  demo script pattern, adapter pitfall index

Root AGENTS.md condensed from 527 → 398 lines. Reviewed 4 agent-related
notes for overlap; added cross-ref to agentic-workflow.md.

PR: <https://github.com/CERTCC/Vultron/pull/581>
