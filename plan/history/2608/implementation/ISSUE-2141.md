---
source: ISSUE-2141
timestamp: '2026-08-10T21:10:09.426979+00:00'
title: gate invite-path RM triage on Finder replica in 4 demo scenarios
type: implementation
---

Issue: #2141 — Bug: 4 full-suite demo scenarios have unguarded invite-path CLP-08-005

Symptoms: fccv-handoff, fvcv-extension, fccv-extension, fvv demos intermittently
fail with ReconstructChainTailNode raising an unanchored-chain error. Root cause:
the Finder receives Announce(CaseLedgerEntry) broadcast by run_invite_path_rm_triage
before its genesis VulnerabilityCase hash is seeded (CLP-08-005 race).

Root cause: invite-path RM triage triggers a ledger entry announcement to all
participants including the Finder. If the Finder's genesis VulnerabilityCase
hasn't been replicated yet, the chain tail reconstruction fails.

Fix: Added wait_for_case_on_container(finder_client, case.id_) immediately before
run_invite_path_rm_triage in 4 phase functions:

- fccv_handoff_demo._phase_c2_invites_vendor (+ finder_client param added)
- fvcv_extension_demo._phase_coordinator_suggests_vendor2 (+ finder_client param added)
- fccv_extension_demo._phase_c2_suggests_vendor (+ finder_client param added)
- fvv_demo._phase_report_submission (finder_client already present)

Regression tests added to all 4 test files (TestFinderCaseReplicaWaitBefore*Triage),
verifying signature presence and wait-before-triage ordering.

PR: <https://github.com/CERTCC/Vultron/pull/2165>
