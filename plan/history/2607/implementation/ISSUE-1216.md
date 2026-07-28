---
source: ISSUE-1216
timestamp: '2026-07-22T20:50:45.745642+00:00'
title: FCCV-handoff demo (DEMOMA-14)
type: implementation
---

## Issue #1216 — FCCV-handoff demo

Implemented the FCCV-handoff CVD scenario where C1 (Coordinator1) creates a case as CASE_OWNER, transfers ownership to C2 (Coordinator2) via TRIG-11-001/002, and C2 invites Vendor. Full lifecycle through VFDPxa + EM.EXITED + RM.CLOSED.

New files: fccv_handoff_demo.py, seed_containers_fccv(), fccv-handoff CLI command, DEMOMA-14 spec group (9 specs), fccv-handoff CI job, 14 unit tests, case-ledger invariant harness.

PR: <https://github.com/CERTCC/Vultron/pull/1628>
Follow-up: #1626 (remove unused actor params from _phase_dump_case_ledgers)
