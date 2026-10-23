---
source: ISSUE-2120
timestamp: '2026-08-08T02:02:37.323601+00:00'
title: gate invite-path RM triage on Finder having case replica
type: implementation
---

Bug #2120: CLP-08-005 unanchored chain bootstrap in fcvcv and fvcv-handoff demos.

Root cause: run_invite_path_rm_triage fired before Finder's VulnerabilityCase
(genesis hash) was seeded in DataLayer, causing ReconstructChainTailNode to
raise CLP-08-005 when processing Announce(CaseLedgerEntry).

Fixed by adding wait_for_case_on_container(finder_client, case.id_) before each
of 3 run_invite_path_rm_triage call sites:

- _phase_report_submission (V1 triage) in fcvcv_demo.py
- _phase_c2_suggests_v2 (V2 triage) in fcvcv_demo.py — also added finder_client param
- _phase_coordinator_invites_vendor2 (Vendor2 triage) in fvcv_handoff_demo.py — also added finder_client param

5 regression tests added (3 in new test_fcvcv_demo.py, 2 in test_fvcv_handoff_demo.py)
verifying call-ordering invariant.

PR: <https://github.com/CERTCC/Vultron/pull/2127>

Follow-up PR #2151: added the missing genesis-level wait in `_phase_report_submission`
(immediately after `wait_for_case_participants`) in both `fcvcv_demo.py` and
`fvcv_handoff_demo.py`. PR #2127 addressed late-phase triage waits; this PR
addresses the earlier race where `Announce(CaseLedgerEntry)` arrives before
`Create(VulnerabilityCase)` is seeded. Regression tests added:
`TestFinderCaseReplicaGenesisWaitInReportSubmission` in both test files.

PR: <https://github.com/CERTCC/Vultron/pull/2151>
