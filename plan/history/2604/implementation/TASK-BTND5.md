---
title: "TASK-BTND5.1: Add CVDRoles.CASE_OWNER"
type: implementation
timestamp: '2026-04-30T19:55:29+00:00'

source: TASK-BTND5
---

## TASK-BTND5.1 — Add `CVDRoles.CASE_OWNER`

Added `CASE_OWNER = auto()` to the `CVDRoles` Flag enum in
`vultron/core/states/roles.py`. The new value (64) is distinct from all
existing roles and is combinable via bitwise OR. Created
`test/core/states/test_cvd_roles.py` with four tests covering existence,
distinctness, combinability, and stability of existing role values.
Spec satisfied: BTND-05-001.
