---
source: ISSUE-1688
timestamp: '2026-07-27T17:00:06.225007+00:00'
title: 'Ledger: case-initialization prologue entries'
type: implementation
---

## Issue #1688 — Ledger: write case-initialization prologue entries at case creation

Implemented WritePrologueLedgerEntriesNode in vultron/core/behaviors/case/nodes/prologue.py. The node back-fills five canonical ledger entries (submit_report, create_case, add_report_to_case, add_participant_status_to_participant, add_case_status_to_case) when the CaseActor accepts its CASE_MANAGER role. Best-effort semantics: returns SUCCESS even when the case is not found (split deployment) or individual commits fail (no genesis hash). Injected as the first effect_node in create_offer_case_manager_role_received_tree() after the CLP-10-006 guarded offer_case_manager_role commit. Also added two canonical payload signatures to chain.py and moved VultronReplicationState import to module level to satisfy BTND-07-004. 15 new tests. PR: <https://github.com/CERTCC/Vultron/pull/1713>
