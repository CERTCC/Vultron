---
source: ISSUE-1454
timestamp: '2026-07-17T15:40:02.229907+00:00'
title: '#1454: P/X/A embargo-eligibility precondition guards'
type: implementation
---

## Issue #1454 — Model P/X/A embargo-eligibility rules as precondition guards

Implemented AC-1 through AC-3. Added `_assert_pxa_embargo_eligible()` static helper to `EmbargoLifecycle`. Guards enforce EMB-01-002 (propose), EMB-02-002 (accept, owner-only), and EMB-04-002 (reject from REVISE). OBSERVED mode bypasses all guards. 79 tests cover all 7 ineligible CS_pxa states parametrically. PR: <https://github.com/CERTCC/Vultron/pull/1483>
