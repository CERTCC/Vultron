---
source: ISSUE-1366
timestamp: '2026-07-15T15:03:24.086748+00:00'
title: define BtNodePreconditionError exception class
type: implementation
---

## Issue #1366 — feat: define BtNodePreconditionError exception class

Added `BtNodePreconditionError(VultronError)` to `vultron/errors.py` as required by ADR-0032 and `notes/bt-integration.md` BT-HELPER-01. This is the prerequisite exception class for BT node helpers to raise instead of returning `None` on precondition failure (#1360 consumer). Updated ADR-0032 Consequences to mark the class as available. Added 7 tests in `test/test_errors.py` covering inheritance, message preservation, exception chaining, catchability, and the canonical update()-catches-helper BT-HELPER-01 stub pattern.

PR: <https://github.com/CERTCC/Vultron/pull/1438>
