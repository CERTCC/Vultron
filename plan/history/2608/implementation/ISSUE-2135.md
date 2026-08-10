---
source: ISSUE-2135
timestamp: '2026-08-10T21:13:37.393493+00:00'
title: 'fix(demo): gate Vendor RM triage on Finder having case replica (Bug #2135)'
type: implementation
---

Closes #2135. The `fcv` demo scenario failed with CLP-08-005 (`ReconstructChainTail`) on
the Finder because `_phase_invite_vendor()` called `run_invite_path_rm_triage()` for Vendor
before confirming the Finder's DataLayer had the `VulnerabilityCase` genesis seed. When
Vendor's RM triage broadcasts `Announce(CaseLedgerEntry)` to all participants, the Finder
received entries before `dl.read(case_id)` could return the case — making the genesis hash
unavailable (CLP-08-005, fail-closed).

Fix: add `wait_for_case_on_container(finder_client, case.id_)` before
`run_invite_path_rm_triage` in `_phase_invite_vendor()`, and thread `finder_client` as a
new parameter. Matches the pattern from PR #2127 for `fcvcv_demo.py`.

Added `TestFinderCaseReplicaWaitBeforeVendorTriage` regression class (3 tests) verifying
the ordering invariant (spec CLP-08-005).

PR: <https://github.com/CERTCC/Vultron/pull/2166>
