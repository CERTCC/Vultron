---
source: ISSUE-663
timestamp: '2026-06-08T13:41:22.276828+00:00'
title: Case-actor-only broadcast guard
type: learning
---

## 2026-06-02 ISSUE-663 — Case-actor-only broadcast guard

- `BroadcastStatusToPeersNode` needs the current executing actor to match the
  Case Manager before it should fan out participant status updates.
- Tests for the positive broadcast path need a third participant so the case
  manager has at least one non-sender peer to address.

**Promoted**: 2026-06-08 — captured in `AGENTS.md`, `notes/codebase-structure.md`, and `notes/domain-model-separation.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/818>.
