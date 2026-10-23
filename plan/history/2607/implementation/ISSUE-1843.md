---
source: ISSUE-1843
timestamp: '2026-07-30T20:47:51.917767+00:00'
title: StatusAuthorizationCallOutBundle for two-seam status authorization
type: implementation
---

## Issue #1843 — feat: add StatusAuthorizationCallOutBundle for Seam 1 and Seam 2 call-out injection

Added the core-owned `StatusAuthorizationCallOutBundle` (ADR-0046) with its `STATUS_AUTHORIZATION_DETERMINISTIC` singleton and the demo `STATUS_AUTHORIZATION_STOCHASTIC` singleton, and wired a defaulted `call_out` bundle parameter into `add_participant_status_tree` (Seam 1) and `add_case_status_tree` (Seam 2). Both bundle fields default to AlwaysSucceed (BT-23-002); the stochastic singleton uses AlmostAlwaysSucceed (p=0.90) since this production-only two-seam pattern has no named simulator fuzzer nodes. The guard nodes that consume the factories land in blocked siblings #1841 and #1842.

PR: <https://github.com/CERTCC/Vultron/pull/1849>
