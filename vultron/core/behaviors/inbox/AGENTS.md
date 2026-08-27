# AGENTS.md — `vultron/core/behaviors/inbox/`

Agent guidance for inbox-related BT nodes in this package.

> For project-wide BT conventions see
> [`vultron/core/behaviors/AGENTS.md`](../AGENTS.md).

---

## Inbox Test Seam Must Preserve Production Deferral Semantics

(ISSUE-769, 2026-06-08)

A test-only inbox pipeline that reimplements defer/replay logic can drift
from production behavior unless it reuses the same expiry path. When
writing case-deferral tests:

- Set canonical `to` recipients matching the expected actor-scoped queue
  so actor-scoped queues are exercised under the same addressing assumptions
  as inbox processing.
- Do not reimplement the defer/replay path inline in tests — call the
  production code path directly so timing and queue semantics stay aligned.
