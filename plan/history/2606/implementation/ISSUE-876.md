---
source: ISSUE-876
timestamp: '2026-06-11T19:37:25.149110+00:00'
title: Split status/nodes.py into nodes/ subpackage
type: implementation
---

## Issue #876 — Split vultron/core/behaviors/status/nodes.py into nodes/ subpackage

Split the 1281-line `vultron/core/behaviors/status/nodes.py` (17 classes)
into a `nodes/` subpackage following the established `case/nodes/` pattern
(BTND-07-001, BTND-07-003, CS-18-001 through CS-18-004).

### Submodules created

- `nodes/conditions.py` (101 lines) — `VerifySenderIsParticipantNode`
- `nodes/broadcast.py` (432 lines) — `_find_case_manager_id` + 5 peer fan-out nodes
- `nodes/participant_status.py` (560 lines) — 8 nodes for DEMOMA-07-003 steps 2–5
- `nodes/case_status.py` (254 lines) — `CASE_STATUS_ALREADY_PRESENT` + 3 AddCaseStatusToCase nodes
- `nodes/__init__.py` (86 lines) — re-exports all 19 public names for backward compatibility

### Tests added

New `test/core/behaviors/status/nodes/` directory with 32 new per-submodule
tests verifying imports from concrete submodule paths.

All 3186 unit tests pass. Black, flake8, mypy, and pyright clean.

PR: [#907](https://github.com/CERTCC/Vultron/pull/907)
