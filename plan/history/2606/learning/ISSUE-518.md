---
source: ISSUE-518
timestamp: '2026-06-08T13:41:11.705814+00:00'
title: Entrypoint docs drift in demo-facing text
type: learning
---

## 2026-06-02 ISSUE-518 — Entrypoint docs drift in demo-facing text

- The canonical API deployment entrypoint is
  `vultron.adapters.driving.fastapi.main:app`, but demo-facing text can drift
  back to legacy module paths if not centrally referenced.
- We found stale `vultron.api.main:app` strings in demo exchange script output
  and notes. This task updated onboarding docs only; script help-text cleanup
  remains a separate follow-up candidate if those strings become user-facing
  blockers.

**Promoted**: 2026-06-08 — captured in `AGENTS.md`, `notes/codebase-structure.md`, and `notes/domain-model-separation.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/818>.
