---
source: ISSUE-1641
timestamp: '2026-07-27T18:24:22.587807+00:00'
title: Remove three_actor_demo.py and multi_vendor_demo.py
type: implementation
---

## Issue #1641 — Remove three_actor_demo.py and multi_vendor_demo.py

Deleted two legacy demo scripts (three_actor_demo.py, multi_vendor_demo.py) that predated
the CaseProposal protocol, bypassed the BT for case creation, and emitted DeprecationWarnings.
Both are superseded by DEMOMA-12 (FCV) and DEMOMA-11 (FVCV-Handoff) respectively.

Removed: ~1535 lines of demo code, 309 lines of tests, 125 lines of CLI wiring.
Updated docs/tutorials to reflect the current 6-scenario landscape.
AC-4 audit confirmed no unique scenario ideas were lost.

PR: <https://github.com/CERTCC/Vultron/pull/1720>
