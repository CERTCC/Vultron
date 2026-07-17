---
source: ISSUE-1453
timestamp: '2026-07-17T15:19:26.475966+00:00'
title: Add RM/vfd/EM/pxa ratchet predicates and state-group tuples
type: implementation
---

## Issue #1453 — Add RM/vfd/EM/pxa ratchet predicates and state-group tuples

Implemented LST-04-001 ratchet predicates and state-group tuples in vultron/core/states/:

- RM: RM_VALIDATED tuple + is_rm_validated() (excludes RM.CLOSED, reachable without validation)
- EM: EM_EMBARGO_ACTIVE tuple + is_em_embargo_active() (ACTIVE + REVISE states)
- vfd: VFD_VENDOR_AWARE/FIX_READY/FIX_DEPLOYED tuples + is_vfd_*() predicates
- pxa: PXA_PUBLIC_AWARE/EXPLOIT_PUBLIC/ATTACKS_OBSERVED tuples + is_pxa_*() predicates
- New test file test/core/states/test_ratchet_predicates.py with parametrized + exhaustive coverage
- Fixed CS_pxa docstring: pXa/pXA are ephemeral not invalid states

PR: <https://github.com/CERTCC/Vultron/pull/1482>
