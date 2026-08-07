---
source: ISSUE-2025
timestamp: '2026-08-06T18:25:39.453722+00:00'
title: 'fix(demo): correct case closure ordering in fvcv_extension and fccv_handoff'
type: implementation
---

## Issue #2025 — fix(demo): correct case closure ordering in fvcv_extension and fccv_handoff scenarios

Fixed the case-owner-closes-last ordering violation in two demo scenarios:

- `fvcv_extension_demo.py`: moved Vendor1 (CASE_OWNER throughout) to close last
- `fccv_handoff_demo.py`: moved C2 (CASE_OWNER post-handoff) to close last

Added regression tests to both test files mirroring the pattern established in PR #2021.

DEFER: pre-existing c1_client used as authoritative ledger source post-handoff in fccv_handoff — tracked in #2043.

PR: <https://github.com/CERTCC/Vultron/pull/2045>
