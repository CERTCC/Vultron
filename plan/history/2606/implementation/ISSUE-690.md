---
source: ISSUE-690
timestamp: '2026-06-09T16:19:08.145144+00:00'
title: Fix case log observability artifacts
type: implementation
---

## Issue #690 — [Feature] Fix case log observability: missing case-actor log, empty payloadSnapshot, replication gaps

Implemented payload snapshot propagation from `CommitCaseLogEntryNode` into the commit tree so case-log entries receive normalized activity payloads instead of defaulting to empty objects. Updated two-actor demo log dumping to always emit a case-actor JSONL artifact, using the dedicated case-actor client when available and falling back to the vendor container's case-actor sub-actor route key when the dedicated service has no entries.

PR: <https://github.com/CERTCC/Vultron/pull/845>
