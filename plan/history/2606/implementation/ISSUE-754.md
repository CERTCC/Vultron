---
source: ISSUE-754
timestamp: '2026-06-05T20:25:20.756815+00:00'
title: Split vultron/core/behaviors/sync/nodes.py into nodes/ subpackage
type: implementation
---

## Issue #754 — Split vultron/core/behaviors/sync/nodes.py into nodes/ subpackage

### Summary

Refactored flat `vultron/core/behaviors/sync/nodes.py` (693 lines, 15 node classes) into a `nodes/` subpackage grouped by semantic domain, per BTND-07-001/002.

### Implementation Details

**Source refactoring:**

- `conditions.py`: 5 condition nodes (CheckIsOwnCaseActorNode, CheckIsNotOwnCaseActorNode, VerifySenderIsOwnIdNode, CheckLogEntryAlreadyStoredNode, IsNotRemoveEmbargoEventNode)
- `receive.py`: 3 action nodes for receive/validation (LogDeliveryConfirmationNode, PersistReceivedLogEntryNode, CheckHashOrRejectOnMismatchNode)
- `chain.py`: 4 action nodes for chain reconstruction (ReconstructChainTailNode, UpdateReplicationStateNode, CreateLogEntryNode, PersistLogEntryNode)
- `replay.py`: 3 action nodes for replay/fan-out (FindCaseActorNode, ReplayMissingEntriesNode, FanOutLogEntryNode)
- `__init__.py`: Re-exports all public names and helper functions for backward compatibility

**Test suite mirrored:**

- `conftest.py`: Shared fixtures and helper functions
- `test_conditions.py`, `test_receive.py`, `test_chain.py`, `test_replay.py`: Per-submodule unit tests

### Verification

✅ All 3006 tests pass
✅ Linters clean: flake8, mypy, pyright
✅ Existing imports continue to work (embargo/nodes.py, sync tree files)
✅ All AC criteria met

**PR**: <https://github.com/CERTCC/Vultron/pull/815>
