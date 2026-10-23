---
source: ISSUE-1266
timestamp: '2026-07-08T19:02:48.278578+00:00'
title: 'FUZZ-08a-quart: Reclassify remaining Sentinel-labeled fuzzer nodes'
type: implementation
---

## Issue #1266 — FUZZ-08a-quart: Reclassify remaining 17 Sentinel-labeled nodes

Completed audit of all 17 nodes listed in #1266. Reclassified the final two nodes that still carried the Sentinel label:

- EmbargoTimerExpired → Retriever (BT-tick-driven synchronous timestamp comparison; BT-18-006)
- MonitorDeployment → Actuator (fire-and-confirm side-effect executor; no content artifact)

All other 15 nodes (NoNewValidationInfo, NoNewPrioritizationInfo, NoNewDeploymentInfo, ExploitPrioritySet, ExploitDeferred, ExploitDesired, AllPublished, PublicationIntentsSet, ExploitReady, NotificationsComplete, RcptNotInQrmS, MoreVendors, MoreCoordinators, MoreOthers, IsIDAssignmentAuthority) were already reclassified to ProtocolInternal in prior PRs.

With zero Sentinel-labeled BT nodes remaining, issue #1175 (FUZZ-08f — Implement all Sentinel-shaped call-out points) was closed: its scope reached zero.

PR: <https://github.com/CERTCC/Vultron/pull/1273>
