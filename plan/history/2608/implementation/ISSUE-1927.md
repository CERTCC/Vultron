---
source: ISSUE-1927
timestamp: '2026-08-03T21:01:39.016218+00:00'
title: add VENDOR-or-DEPLOYER guard tests for verify_fix_deployed
type: implementation
---

## Issue #1927 — test: add VENDOR-or-DEPLOYER guard tests for verify_fix_deployed (DEMOMA-15-001)

Added unit tests for the `_assert_deployer_or_vendor_role` guard in `vultron/demo/helpers/milestones.py`, covering ACs 5c, 5d, and 5e. AC-5b was already covered by the existing test suite.

PR: <https://github.com/CERTCC/Vultron/pull/1960>
