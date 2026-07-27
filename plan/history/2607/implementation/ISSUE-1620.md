---
source: ISSUE-1620
timestamp: '2026-07-27T20:23:09.690408+00:00'
title: FCCV-extension scenario script, CLI, CI job, invariant tests
type: implementation
---

## Issue #1620 — FCCV-extension scenario

Implemented full FCCV-extension CVD demo: Finder + C1 (CASE_OWNER/Coordinator1) + C2 (Coordinator2/participant) + Vendor.

- Created `vultron/demo/scenario/fccv_extension_demo.py` (8 phases, ADR-0026 suggest-actor flow, VFD path on Vendor only)
- Added `fccv-extension` CLI command to `vultron/demo/cli.py`
- Added fccv-extension entries to both CI matrices in `.github/workflows/demo-integration.yml`
- Created `test/ci/invariants/test_fccv_extension_invariants.py` (42 tests)
- Updated `notes/demo-future-ideas.md` to show FCCV-extension as implemented

PR: <https://github.com/CERTCC/Vultron/pull/1743>
