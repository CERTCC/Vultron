---
source: ISSUE-1891
timestamp: '2026-08-03T20:48:00.308948+00:00'
title: create_terminate_active_embargo_tree factory
type: implementation
---

## Issue #1891 — FUZZ-08a-ter: create_terminate_active_embargo_tree factory

Implemented the actor-voluntary active embargo termination BT factory (EMB-14).

### What was built

- `create_terminate_active_embargo_tree` in `vultron/core/behaviors/embargo/terminate_active_embargo_tree.py`
- 5-child memory=False Sequence: HasActiveEmbargoNode → ReasonSelector → AuthorizeEmbargoExit → OnEmbargoExit → terminate_embargo_bt
- `EmbargoExitPolicyGuard` and `EmbargoExitOverride` fuzzer stubs in `vultron/demo/fuzzer/embargo.py`
- Stochastic factories wired into `EMBARGO_STOCHASTIC` in `vultron/demo/fuzzer/bundles/embargo.py`
- 33 tests covering structure, memory=False regression guards, ceiling/floor, factory injection, result_out propagation

### Notable discovery

`EmbargoExitPolicyGuard` and `EmbargoExitOverride` were fully designed in the notes/spec but had zero implementation — both were created as part of this issue.

PR: <https://github.com/CERTCC/Vultron/pull/1957>
