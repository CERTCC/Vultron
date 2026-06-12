---
source: ISSUE-889
timestamp: '2026-06-12T20:21:46.438416+00:00'
title: Move composite BT subtrees to *_tree.py modules (BTND-07-003)
type: implementation
---

## Issue #889 — Move composite Sequence/Selector subclasses from nodes/ subpackage to \*\_tree.py modules (BTND-07-003)

Moved the five `Sequence`/`Selector` composite subclasses that were
incorrectly living in the `nodes/` leaf-node subpackage to dedicated
`*_tree.py` modules at the process-area root, satisfying BTND-07-003.

**New modules:**

- `case_setup_tree.py`: `RecordCaseCreationEvents`, `CreateCaseActorNode`
- `participant_tree.py`: `SeedParticipantAsSignatoryIfEmbargoActiveNode`,
  `CreateCaseOwnerParticipant`, `CreateCaseParticipantNode`

**Backward compat:** `nodes/__init__.py` and `nodes/participant/__init__.py`
re-export the moved classes via PEP 562 module `__getattr__` (lazy import at
first access) with `TYPE_CHECKING` stubs for mypy. This avoids the circular
import that arises because the tree modules import leaf nodes from `nodes/`.

**Callers updated:** `create_tree.py` and `receive_report_case_tree.py` now
import composites from the canonical tree modules directly.

All 3205 unit tests pass. Black, flake8, mypy, pyright clean.

PR: <https://github.com/CERTCC/Vultron/pull/942>
