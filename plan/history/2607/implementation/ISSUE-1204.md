---
source: ISSUE-1204
timestamp: '2026-07-08T16:26:38.432460+00:00'
title: Unify embargo termination BT — routing-gated shared factory (BT-19)
type: implementation
---

## Issue #1204 — Unify embargo termination BT: routing-gated shared factory (BT-19)

Replaced monolithic `TerminateEmbargoNode` (committed EM state before verifying routing) with shared `terminate_embargo_bt` factory enforcing BT-19-001 ordering. Both trigger path and cascade path now use the same factory (BT-19-002). Pre-PR code review caught 4 findings (active-embargo guard preventing AutoClose halt, memory=True on Sequence, outbox write test assertion). PR: <https://github.com/CERTCC/Vultron/pull/1263>
