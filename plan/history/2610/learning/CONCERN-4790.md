---
source: CONCERN-4790
timestamp: '2026-10-16T20:09:54.806191+00:00'
title: EmbargoLifecycle.terminate_active_embargo has no production caller left
type: learning
---

## Concern

`EmbargoLifecycle.terminate_active_embargo` (`vultron/core/services/embargo_lifecycle/activation.py`) is no longer called anywhere under `vultron/`. A search for `terminate_active_embargo` finds only its definition and two docstring mentions (`embargo_lifecycle/__init__.py`, `service.py`). Termination now goes through the copy model: the CASE_MANAGER's termination arm commits the `Remove` entry and applies the `TERMINATE` step (#4714), and the replica's teardown slot copies that step.

The method, including its `OBSERVED` branch, survives only in tests (for example `test/core/services/embargo_lifecycle/test_activation.py` and `test_base.py`). Those tests pin behaviour that no production path exercises.

## Why it matters

Code with no production caller looks like a supported path. A new caller could reach for it, and running it in `OBSERVED` mode on a replica would break CM-23-016. Its tests also cost maintenance and suggest coverage the real termination path does not get from them.

## Options

1. Remove the method and its tests. Before removing anything, check that every rule those tests pin (EP-08-004 cancel of every open proposal, the cleared relay index) is also pinned on the termination copy path (`test/core/use_cases/received/test_embargo_termination_copy.py`, `test/core/behaviors/embargo/nodes/test_teardown.py`).
2. Keep it as a STRICT-only helper that the termination arm calls, and remove the `OBSERVED` branch.

Found while building #4784.

Where: vultron/core/services/embargo_lifecycle/activation.py

**Resolved**: 2026-10-16 — implementation tracked in #4846.
Decision: remove the method and its own tests (option 1). The copy path already checks proposal cancel (EP-08-004) and the cleared relay index (EP-08-003, in `test_teardown.py`); fixtures move to `test/support/embargo_register.terminate()`; spec EMB-18-001 is edited with the code. No ADR, notes or spec changes in the planning PR.
