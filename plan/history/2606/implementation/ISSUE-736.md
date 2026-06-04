---
source: ISSUE-736
timestamp: '2026-06-04T13:37:31.879483+00:00'
title: Split case nodes.py into nodes/ subpackage
type: implementation
---

## Issue #736 — Split vultron/core/behaviors/case/nodes.py into a nodes/ subpackage

Split the 1502-line monolithic `vultron/core/behaviors/case/nodes.py` into a
`nodes/` subpackage organized by semantic domain:

- `conditions.py`: `CheckCaseAlreadyExists`, `CheckCaseExistsForReport`,
  `ValidateCaseObject`
- `case_setup.py`: `PersistCase`, `SetCaseAttributedTo`,
  `RecordCaseCreationEvents`, `CreateCaseActorNode`
- `participant.py`: `_create_and_attach_participant` helpers +
  `CreateCaseOwnerParticipant`, `CreateCaseParticipantNode`
- `embargo.py`: `_DEFAULT_EMBARGO_DAYS`, helpers, `InitializeDefaultEmbargoNode`
- `communication.py`: `EmitCreateCaseActivity`, `SendOfferCaseManagerRoleNode`
- `lifecycle.py`: `CommitCaseLogEntryNode`
- `__init__.py`: re-exports all 13 classes + `UpdateActorOutbox` +
  `_create_and_attach_participant` (backward-compatible public path)

All existing import paths via `vultron.core.behaviors.case.nodes` continue to
work without modification. Tests migrated from monolithic test files to matching
submodule test files; added real unit tests for condition nodes and
`InitializeDefaultEmbargoNode`. All 2661 tests pass.

PR: [#744](https://github.com/CERTCC/Vultron/pull/744)
