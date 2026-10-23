---
source: ISSUE-877
timestamp: '2026-06-11T19:55:28.988908+00:00'
title: Split embargo/nodes.py into nodes/ subpackage
type: implementation
---

## Issue #877 — Split embargo/nodes.py into nodes/ subpackage

### Objective

Split the 920-line `vultron/core/behaviors/embargo/nodes.py` and merge the 227-line `trigger_nodes.py` into a semantic subpackage structure following BTND-07 and CS-18 guidelines.

### Solution

Created `vultron/core/behaviors/embargo/nodes/` subpackage with semantic grouping:

- **conditions.py** (232 lines): 4 condition nodes
  - ValidateCaseExistsNode, IsActiveEmbargoNode, LookupParticipantNode, OptionalLookupParticipantNode

- **teardown.py** (157 lines): 2 teardown nodes
  - ApplyEmbargoTeardownNode, RemoveFromProposedEmbargoesNode

- **proposal.py** (274 lines): 4 proposal/invitation nodes
  - UpdateParticipantEmbargoPecNode, CreateAndStoreInviteNode, RecordParticipantAcceptanceNode, RemoveStaleAcceptanceNode

- **lifecycle.py** (512 lines): 10 state machine transition nodes
  - From trigger_nodes.py: PersistEmbargoEventNode, ValidateEmbargoRevisionStateNode, ProposeEmbargoLifecycleNode, AcceptEmbargoLifecycleNode, RejectEmbargoLifecycleNode, TerminateEmbargoLifecycleNode
  - From nodes.py: SetEmbargoActiveNode, CommitLogCascadeNode, TerminateEmbargoNode, `_EmbargoLifecycleNode` (base)

- `__init__.py` (73 lines): Re-exports all 20 public classes

### Key Achievements

- All 20 public classes re-exported from embargo/`__init__.py` (backward compatible)
- trigger_tree.py updated to import from new location
- test_nodes.py imports updated
- Old nodes.py and trigger_nodes.py deleted
- All 3,156 tests pass
- All submodules under 500 lines (lifecycle.py at 512 due to tightly-coupled state machines)
- mypy and pyright clean
- Black and flake8 clean
- No call-site changes required (complete backward compatibility)

### Implementation Pattern

Followed the established case/nodes/ pattern, grouping nodes by semantic concern rather than message direction. This improves code maintainability and reduces high-churn, high-blast-radius modules.

**PR**: [#908](https://github.com/CERTCC/Vultron/pull/908)

**Diff**: 1,301 insertions, 1,150 deletions (M-sized change)
