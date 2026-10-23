---
source: ISSUE-1421
timestamp: '2026-07-14T19:33:53.241273+00:00'
title: 'fix: extract _ensure_reporter_participant to behaviors layer (ISSUE-1421)'
type: implementation
---

## Issue #1421 — fix: extract _ensure_reporter_participant to shared module (BT→use_case import violation)

Moved `_ensure_reporter_participant` and `_upgrade_participant_to_accepted` from `vultron/core/use_cases/received/case/_helpers.py` into `vultron/core/behaviors/case/nodes/participant/common.py`, eliminating a BT→use_cases import-direction violation (AGENTS.md BT-IDM-02).

`EnsureReporterParticipantAtAcceptedNode` previously hid the violation behind a deferred import inside `update()`. The fix moves the functions to the behaviors layer and adds backward-compat `# noqa: F401` re-exports in `_helpers.py`.

Pre-PR code review found a pre-existing sibling violation: `common.py` still imports `_as_id`/`_report_phase_status_id` from `use_cases._helpers`. Filed as follow-up #1428.

PR: <https://github.com/CERTCC/Vultron/pull/1429>
