---
source: TASK-CP-CLEANUP
timestamp: '2026-05-04T20:37:41.019631+00:00'
title: Remove deprecated CasePersistence compat methods
type: implementation
---

Removed deprecated `get()` and `by_type()` methods from the `CasePersistence` and `CaseOutboxPersistence` narrow port protocols. Migrated all 11 call sites across `vultron/core/` to use `read()` and `list_objects()` (typed, vocabulary-aware replacements). Updated `UpdateObject` BT helper to handle `PersistableModel` inputs. Updated `test/core/behaviors/test_helpers.py` to use `VulnerabilityReport` fixtures (registered in vocabulary) instead of generic `Record` objects. All 2285 tests pass.
