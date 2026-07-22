---
source: ISSUE-1311
timestamp: '2026-07-22T16:39:26.616642+00:00'
title: Production Collapse 3 — notification loop
type: implementation
---

## Issue #1311 — FUZZ-08c: Production Collapse 3 (Notification Loop)

Upgraded `create_report_to_others_tree` from Phase 1 stub to full Phase 2 implementation per ADR-0029 / BT-20-003.

Key changes:

- New `_WriteRolesNode` ProtocolInternal node writes `suggested_roles_{case_id_segment}` before each sub-loop trigger (BTND-03-004, AC-2)
- New `_make_role_sub_loop` helper builds BTND-08-001 skip-or-execute Selector arms for vendor/coordinator/other typed sub-loops
- `InjectParticipant`/`InjectVendor`/`InjectCoordinator`/`InjectOther` Actuator nodes replaced by `suggest_*_factory` call-out points (AC-1)
- 38 Phase 2 tests covering all 5 ACs
- ADR-0029 finalized (proposed → accepted), BT-20-003 PROVISIONAL removed (AC-5)

PR: <https://github.com/CERTCC/Vultron/pull/1599>
