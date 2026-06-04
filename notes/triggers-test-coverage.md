---
title: "Trigger Use-Case Test Coverage and PR Scope"
status: active
description: >
  Coverage expectations and PR-scope discipline for trigger use cases in
  vultron/core/use_cases/triggers/, motivated by repeated high-churn in
  case.py without per-use-case regression tests.
---

# Trigger Use-Case Test Coverage and PR Scope

## Background

`vultron/core/use_cases/triggers/case.py` accumulated 26 commits in 90 days
(originating concern: [#652](https://github.com/CERTCC/Vultron/issues/652)).
Two structural properties amplify the risk of regressions in this file:

1. **Multiple use cases per module.** As of the originating concern, `case.py`
   contained six trigger use cases (`SvcEngageCaseUseCase`,
   `SvcDeferCaseUseCase`, `SvcCreateCaseUseCase`, `SvcAddObjectToCaseUseCase`,
   `SvcAddReportToCaseUseCase`, `SvcAddParticipantStatusUseCase`). Half of
   them lacked dedicated unit tests — coverage was incidental, via
   `test_trignotify.py` and `test_svc_add_participant_status.py` only.
2. **Co-evolution with embargo logic.** Case-state and embargo-state
   transitions are tightly coupled in the protocol, so many PRs touch case
   triggers and embargo triggers together. When tests are sparse, a regression
   in one can ship silently behind a fix to the other.

## Coverage expectation

Every trigger use case in `vultron/core/use_cases/triggers/` SHOULD have at
least one dedicated unit test that exercises its `execute()` path against a
real (in-memory) `DataLayer` and asserts:

- the use case's state mutation (RM, EM, CS, or PEC transition as applicable);
- the outbox effect (activity queued, addressed correctly per PCR-08-001); and
- the failure modes the use case is documented to raise
  (`VultronValidationError`, `VultronNotFoundError`).

Existing coverage anchors:

| Use case | Dedicated test file |
|---|---|
| `SvcEngageCaseUseCase` | `test/core/use_cases/triggers/test_trignotify.py` |
| `SvcDeferCaseUseCase` | `test/core/use_cases/triggers/test_trignotify.py` |
| `SvcAddParticipantStatusUseCase` | `test/core/use_cases/triggers/test_svc_add_participant_status.py` |
| `SvcCreateCaseUseCase` | *missing — tracked in test-backfill issue* |
| `SvcAddObjectToCaseUseCase` | *missing — tracked in test-backfill issue* |
| `SvcAddReportToCaseUseCase` | *missing — tracked in test-backfill issue* |

When you add a new trigger use case, create the matching `test_<use_case>.py`
file in the same PR. Do not rely on integration coverage in
`test_trignotify.py` or scenario demos to substitute for per-use-case tests.

## PR-scope discipline

Avoid bundling case-trigger and embargo-trigger changes in the same PR
unless the change is intrinsically cross-cutting (e.g., a renaming sweep,
or an `EmbargoLifecycle` (#538) seam refactor that necessarily touches both).
Bundled diffs are the primary failure mode that the originating concern
documented: a reviewer focused on the case-trigger change misses the
embargo regression and vice versa.

When a single PR must touch both, call it out explicitly in the PR body and
list the integration test(s) that exercise the combined path.

## Structural follow-up

The module structure of `triggers/case.py` mirrors the `nodes.py` smell that
[`specs/behavior-tree-node-design.yaml`](../specs/behavior-tree-node-design.yaml)
BTND-07-001 addresses for BT nodes: a flat module accumulating many classes
becomes high-blast-radius and review-hostile. A future split into a
`triggers/case/` subpackage — one submodule per use case — is tracked
separately and is intentionally sequenced **after**
[#711](https://github.com/CERTCC/Vultron/issues/711) lands, so the split
operates on the post-refactor file rather than fighting it.

## References

- Originating concern: [#652](https://github.com/CERTCC/Vultron/issues/652)
- Parallel BT-nodes pattern: `specs/behavior-tree-node-design.yaml`
  BTND-07-001, BTND-07-002
- PCR-08-001 (participant → CaseActor addressing): see
  `notes/case-communication-model.md`
- Trigger-side state machine BT integration: [#711](https://github.com/CERTCC/Vultron/issues/711)
- EmbargoLifecycle consolidation: [#538](https://github.com/CERTCC/Vultron/issues/538)
