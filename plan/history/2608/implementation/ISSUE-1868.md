---
source: ISSUE-1868
timestamp: '2026-08-03T18:58:54.212289+00:00'
title: seed reporter as embargo SIGNATORY (CM-14-005)
type: implementation
---

## Issue #1868 — fix(case-init): seed reporter as embargo SIGNATORY (CM-14-005)

Implemented CM-14-005: reporter participant is now seeded as SIGNATORY on any active embargo during case initialization. Added _SeedReporterSignatoryNode BT node to case_proposal_received_tree.py, inserted after _SeedVendorOwnerSignatoryNode and before_CommitNativeLedgerEntriesNode. Uses apply_pec_transition(PEC_Trigger.ACCEPT) — the authoritative consent-write path per CM-18-005, CM-18-006, ADR-0048. Six tests added covering all 5 ACs plus graceful-degradation. PR: <https://github.com/CERTCC/Vultron/pull/1938>
