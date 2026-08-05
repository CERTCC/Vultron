---
source: ISSUE-1976
timestamp: '2026-08-05T20:05:04.288292+00:00'
title: pytest coverage sweep — invariant fixtures, milestone assertions, chain tests,
  PEC chain
type: implementation
---

## Issue #1976 — pytest coverage sweep

Adds 3044 lines of tests across six acceptance criteria:

- AC-1: test/ci/invariants/ — conftest.py + test_common.py (negative invariant cases) + test_late_joiner.py (late-joiner gap/ordering)
- AC-2: test/core/use_cases/triggers/case/ — explicit milestone assertions in 6 trigger-use-case files
- AC-3: test/core/use_cases/test_receive_report_chain.py — ValidateReport→EngageCase chain integration test (pre-seeds DataLayer with VultronOfferRecord + vulnerability_reports link so EnsureEmbargoExists resolves)
- AC-4: test/demo/ — milestone assertion tests for all *phase** functions across all 6 scenario demo files; test_fccv_extension_demo.py created as new file
- AC-5: test/core/behaviors/case/test_multi_participant_pec_chain.py — NO_EMBARGO→INVITED→SIGNATORY PEC chain via BTTestScenario for two independent participants
- AC-6: test_fccv_extension_demo.py (new) — CLI smoke tests + milestone assertions

PR: <https://github.com/CERTCC/Vultron/pull/2005>
