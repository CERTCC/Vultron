---
source: ISSUE-1687
timestamp: '2026-07-27T14:13:03.622952+00:00'
title: 'BT: emit Announce(EmbargoEvent) after embargo teardown'
type: implementation
---

## Issue #1687 — BT: emit Announce(EmbargoEvent) after embargo teardown

Added SendAnnounceEmbargoEventNode after ApplyEmbargoTeardownNode in the ActiveTeardown Sequence of remove_embargo_from_case_tree. Node resolves Case Manager, builds Announce(EmbargoEvent) via factory, queues to outbox. Best-effort semantics (SUCCESS + WARNING) when factory absent or no Case Manager found. Extracted make_case_with_manager() to shared conftest. 5 unit tests + 3 integration tests. Deferred factory-dispatch base class extraction to #1707.

PR: <https://github.com/CERTCC/Vultron/pull/1709>
