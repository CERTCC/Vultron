---
source: ISSUE-1057
timestamp: '2026-07-06T20:14:42.635763+00:00'
title: ARCH-14 wire vocab naming-ratchet and parity tests
type: implementation
---

## Issue #1057 — test: add architecture parity and naming-ratchet tests for wire vocab objects (ARCH-14)

Added two architecture tests to enforce ARCH-14-001 going forward:

1. `test/architecture/test_wire_vocab_naming.py` — ratchet asserting no wire `vocab/objects/` class shares a bare name with a core model class. Documents 16 known pre-existing collisions in `KNOWN_VIOLATIONS`; new collisions fail immediately.
2. `test/core/models/test_case.py::TestWireVulnerabilityCaseFieldParity` — asserts wire `VulnerabilityCase` has no fields absent from core (ARCH-09-001 superset invariant).

Code review finding resolved: `assert not core_only` block dropped because ARCH-09-001 requires core >= wire (superset), not strict equality.

PR: [#1220](https://github.com/CERTCC/Vultron/pull/1220)
