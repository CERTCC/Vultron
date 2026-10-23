---
source: ISSUE-489
timestamp: '2026-05-18T13:39:09.660836+00:00'
title: Extract shared demo helpers into vultron/demo/helpers/
type: implementation
---

Extracted scenario-agnostic helper functions from `vultron/demo/scenario/two_actor_demo.py` (~2050 lines) into a new `vultron/demo/helpers/` package.

New sub-modules: polling.py (wait_for_*helpers + *poll_until), actions.py (actor_notifies** wrappers), seeding.py (_dl_key, get_actor_by_id, seed_containers), sync.py (SYNC-2 trigger_log_commit, verify_replica_state), verification.py (assertion primitives). Full re-export **init**.py preserves all module-level names for backward compatibility.

The scenario file shrank from ~2050 to ~1210 lines. reset_containers was retained in-place because tests patch vultron.demo.scenario.two_actor_demo.reset_datalayer.

Key constraint handled: verify_replica_state kept original parameter names (finder_client/vendor_client) to match test call sites.

All 2592 tests pass (full suite including integration). mypy, pyright, black, flake8 clean. PR #541 closes Issue #489.
