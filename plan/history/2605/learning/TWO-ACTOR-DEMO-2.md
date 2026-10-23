---
source: TWO-ACTOR-DEMO-2
timestamp: '2026-05-13T20:27:50.540853+00:00'
title: 'Case Actor spawning: CASE_MANAGER role delegation automation (#469)'
type: learning
---

## 2026-05-08 TWO-ACTOR-DEMO — Case Actor spawning blocks #463

**Issue**: Issue #463 (Two-actor demo, complete VFDPxa workflow) cannot be
implemented until Case Actor spawning and CASE_MANAGER delegation automation
are in place (tracked in new Issue #469, linked as sub-issue of #463).

**Root cause**: `_run_submit_report_case_creation` in `received/report.py`
calls `create_receive_report_case_tree` without an `actor_config`, so the
Vendor participant is created with only `[CVDRole.CASE_OWNER]`, not
`CASE_MANAGER`.

**Three non-trivial missing pieces** (consolidated into #469):

1. Case Actor spawning BT node in `receive_report_case_tree.py`
2. `OfferCaseManagerRoleReceivedUseCase` auto-accept + embargo init
3. `AcceptCaseManagerRoleReceivedUseCase` trust bootstrap

**Promoted**: 2026-05-13 — Issue #469 was closed 2026-05-08; fix already
landed on `task/463-two-actor-demo-replacement`. No new docs needed;
implementation gap is resolved. Archived without further promotion.
