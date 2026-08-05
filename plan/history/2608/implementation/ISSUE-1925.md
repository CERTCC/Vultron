---
source: ISSUE-1925
timestamp: '2026-08-03T21:14:39.295225+00:00'
title: implement fcvcv_demo.py scenario script + fcvcv CLI command
type: implementation
---

## Issue #1925 — feat: implement fcvcv_demo.py scenario script + fcvcv CLI command

Implemented the FCVCV 5-party CVD demo scenario (DEMOMA-19) in full.

### Deliverables

- `vultron/demo/scenario/fcvcv_demo.py`: 8-phase orchestrator
  (report_submission → c2_suggests_v2 → sync_verification → notes_exchange →
  fix_lifecycle → publication → case_closure → dump_case_ledgers)
- `vultron/demo/cli.py`: `fcvcv` subcommand (AC-3b)
- `.github/workflows/demo-integration.yml`: fcvcv matrix entry + actor6 log
  collection (AC-3c)
- `test/ci/invariants/test_fcvcv_invariants.py`: 46-test invariant harness (AC-3d)

### Key spec points implemented

- V1 (VENDOR only) → VFd; V2 (VENDOR+DEPLOYER) → VFD (DEMOMA-19-004)
- V1 publishes first → wait EM.EXITED → V2/C2/C1/Finder publish (DEMOMA-19-005)
- C2 uses ADR-0026 suggest-actor flow for V2 with polling-only delivery (DEMOMA-19-009)
- Devlog actor names: finder, c1, v1, c2, v2, case-actor (DEMOMA-19-007)
- All 9 DEMOMA-19 spec entries satisfied (19-001 and 19-002 were done in prior PR #1945)

PR: <https://github.com/CERTCC/Vultron/pull/1962>
