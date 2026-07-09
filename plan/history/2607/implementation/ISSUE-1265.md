---
source: ISSUE-1265
timestamp: '2026-07-08T18:31:54.697779+00:00'
title: FVV demo scenario (Finder → Vendor1 → Vendor2)
type: implementation
---

## Issue #1265 — Implement FVV demo scenario: Finder → Vendor1 → Vendor2 (no coordinator)

Implemented the FVV three-actor CVD demo scenario. Created fvv_demo.py following two_actor_demo.py phase structure, extended helpers/seeding.py with seed_containers_fvv(), added vultron-demo fvv CLI command, parallel CI job, and 9 unit tests. PR: <https://github.com/CERTCC/Vultron/pull/1270>
