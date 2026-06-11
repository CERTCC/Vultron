---
source: ISSUE-769
timestamp: '2026-06-11T18:35:25.467326+00:00'
title: Inbox test seam must preserve production deferral semantics
type: learning
---

## 2026-06-08 ISSUE-769 — Inbox test seam must preserve production deferral semantics

- A test-only inbox pipeline that reimplements defer/replay logic can drift
  from production behavior unless it reuses the same expiry path.
- Case deferral tests should set canonical `to` recipients so actor-scoped
  queues are exercised under the same addressing assumptions as inbox
  processing.

**Promoted**: 2026-06-11 — captured in `notes/bt-integration.md` §
"Inbox Test Seam Must Preserve Production Deferral Semantics".
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
