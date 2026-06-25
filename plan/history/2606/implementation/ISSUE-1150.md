---
source: ISSUE-1150
timestamp: '2026-06-25T17:44:05.703683+00:00'
title: 'FUZZ-08a: Add new-arch cross-refs and call-out point shapes to fuzzer node
  catalogs'
type: implementation
---

## Issue #1150 — FUZZ-08a: Catalog fuzzer node usage in vultron/bt/ and map to new architecture

Added `new-arch cross-ref` and `call-out point shape` fields to all 93
fuzzer node entries across the four domain catalog files:

- `notes/bt-fuzzer-nodes-embargo.md` (14 nodes)
- `notes/bt-fuzzer-nodes-messaging.md` (1 node)
- `notes/bt-fuzzer-nodes-report-management.md` (75 nodes)
- `notes/bt-fuzzer-nodes-vul-discovery.md` (3 nodes — marked N/A,
  simulation-only BT not ported to new architecture)

Shape distribution: N/A (50), Evaluator (28), Retriever (6), Sentinel (4),
Composer (5). Shapes assigned per the methodology in
`notes/coordination-agents.md`. Cross-references point to the corresponding
`vultron.demo.fuzzer.*` classes created in FUZZ-01–07.

PR: [#1179](https://github.com/CERTCC/Vultron/pull/1179)
