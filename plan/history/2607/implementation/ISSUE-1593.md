---
source: ISSUE-1593
timestamp: '2026-07-22T20:27:12.278650+00:00'
title: FCV three-actor demo scenario (DEMOMA-12)
type: implementation
---

## Issue #1593 — feat: implement FCV demo scenario

Implemented the FCV (Finder + Coordinator + Vendor) three-actor CVD demo scenario per DEMOMA-12.

All 7 ACs delivered:

- AC-1: vultron/demo/scenario/fcv_demo.py — full VFDPxa lifecycle scenario
- AC-2: vultron/demo/helpers/seeding.py — seed_containers_fcv()
- AC-3: vultron/demo/cli.py — fcv CLI command; three-actor command removed
- AC-4: vultron/demo/scenario/three_actor_demo.py — @deprecated decorator applied
- AC-5: .github/workflows/demo-integration.yml — fcv CI job added
- AC-6: test/demo/test_fcv_demo.py — 18 smoke tests
- AC-7/8: test/ci/invariants/test_fcv_invariants.py — invariant tests per DEMOMA-12-008/009

5392 tests pass. PR: <https://github.com/CERTCC/Vultron/pull/1623>
