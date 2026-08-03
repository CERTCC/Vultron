---
source: ISSUE-1924
timestamp: '2026-08-03T20:07:35.977534+00:00'
title: 'feat: add seed_containers_fcvcv (FCVCV)'
type: implementation
---

## Issue #1924 — feat: add seed_containers_fcvcv to seeding.py (FCVCV)

Added `seed_containers_fcvcv` to `vultron/demo/helpers/seeding.py` for the
5-actor FCVCV scenario (DEMOMA-19-002). The function accepts five
`DataLayerClient` args plus five optional deterministic actor ID args, creates
Finder (Person) and four Organization actors (Coordinator1, Vendor1,
Coordinator2, VendorDeployer) in Phase 1, then performs 20 cross-registrations
in Phase 2. Idempotent, matching the pattern of all prior seed functions.

Six integration tests added in `test/demo/test_seed_containers_fcvcv.py`
covering tuple shape, actor names, IDs, peer mesh, deterministic IDs, and
idempotency. Full suite: 6012 passed, 0 new failures.

PR: <https://github.com/CERTCC/Vultron/pull/1946>
