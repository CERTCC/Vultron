---
source: ISSUE-1193
timestamp: '2026-06-26T16:06:59.728937+00:00'
title: Reclassify fuzzer node call-out point shapes
type: implementation
---

## Issue #1193 — FUZZ-08a-ter: Reclassify call-out point shapes and normalize terminology in fuzzer node catalogs

Reclassified all `call-out point shape: N/A` entries in three fuzzer-node
catalog files (embargo, messaging, report-management) using the ADR-0024
seam-structure decision tree, and renamed `automation potential: N/A` to
`TerminalPlaceholder` across all four catalog files.

Changes:

- `notes/bt-fuzzer-nodes-embargo.md`: 4 N/A shapes reclassified
  (`EmbargoTimerExpired`→Sentinel; `OnEmbargoExit`/`OnEmbargoAccept`/`OnEmbargoReject`→Composer)
- `notes/bt-fuzzer-nodes-messaging.md`: 1 N/A shape reclassified
  (`FollowUpOnErrorMessage`→Composer)
- `notes/bt-fuzzer-nodes-report-management.md`: 42 N/A call-out shapes
  reclassified (28 Sentinel, 11 Composer, 2 Retriever, 1 ProtocolInternal);
  automation potential N/A renamed to TerminalPlaceholder for `NoThreatsFound`
- `notes/bt-fuzzer-nodes-vul-discovery.md`: automation potential N/A renamed
  to TerminalPlaceholder for `NoVulFound` only (call-out shapes intentionally
  left as N/A per AC-3)

`NoThreatsFound` is confirmed as the sole ProtocolInternal terminal placeholder
across the three in-scope catalog files. All reclassifications apply the
BT-18-005 / ADR-0024 seam-structure decision tree independently of automation
potential.

PR: [#1195](https://github.com/CERTCC/Vultron/pull/1195)
