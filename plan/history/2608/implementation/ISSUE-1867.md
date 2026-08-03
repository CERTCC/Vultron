---
source: ISSUE-1867
timestamp: '2026-08-03T19:10:36.178551+00:00'
title: 'test(case-init): one participant-status ledger entry per participant; vendor
  is SIGNATORY'
type: implementation
---

## Issue #1867 — feat(case-init): embargo before participant PEC; one status entry per participant (CM-18-007)

Added `TestCM18007InitLedgerEntries` to `test/core/behaviors/case/test_case_proposal_received_tree.py` with two tests:

- `test_exactly_one_participant_status_entry_per_participant` (CM-18-007 AC-3): asserts exactly one `add_participant_status_to_participant` ledger entry per participant, guarding against the two-entry bug (NO_EMBARGO placeholder + correction) that previously broke `log_index` ordering and caused PR #1746 to be reverted.
- `test_vendor_case_owner_appears_as_signatory_in_init_ledger` (CM-14-003 AC-4): asserts the vendor's initialization snapshot carries `emConsentState=SIGNATORY`.

The implementation was already correct (delivered by #1865 + #1866 dependency chain). `notes/case-ledger-authority.md` already documented the one-entry guarantee (AC-5 satisfied). Tests confirmed the behavior; this PR locks it in as a regression guard.

PR: <https://github.com/CERTCC/Vultron/pull/1940>
