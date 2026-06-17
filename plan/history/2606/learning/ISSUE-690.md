---
source: ISSUE-690
timestamp: '2026-06-11T18:36:43.919319+00:00'
title: Case-log snapshots and demo log exports need source-aware fallbacks
type: learning
---

## 2026-06-09 ISSUE-690 — Case-log snapshots and demo log exports need source-aware fallbacks

- `CommitCaseLogEntryNode` must forward a serialized activity payload snapshot
  from the BT blackboard into `create_commit_log_entry_tree()`; otherwise
  `CaseLogEntry.payloadSnapshot` silently defaults to `{}` despite valid
  inbound activity context.
- Two-actor demo log export should always emit a `case-actor` JSONL artifact,
  but dedicated case-actor container reads may be empty in D5-2 by design;
  export logic should fall back to the vendor container's case-actor sub-actor
  route key instead of failing the demo run.

**Promoted**: 2026-06-11 — architectural insight captured; BT blackboard
payload-snapshot handoff pattern is related to the BT result channel guidance
in `notes/bt-integration.md`. Demo fallback is implementation-specific and
not promoted to durable docs.
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
