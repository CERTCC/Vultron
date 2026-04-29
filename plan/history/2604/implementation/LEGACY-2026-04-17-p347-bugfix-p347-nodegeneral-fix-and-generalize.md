---
title: 'P347-BUGFIX + P347-NODEGENERAL: Fix and generalize CreateFinderParticipantNode'
type: implementation
date: '2026-04-17'
source: LEGACY-2026-04-17-p347-bugfix-p347-nodegeneral-fix-and-generalize
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6717
legacy_heading: 'P347-BUGFIX + P347-NODEGENERAL: Fix and generalize CreateFinderParticipantNode'
date_source: git-blame
---

## P347-BUGFIX + P347-NODEGENERAL: Fix and generalize CreateFinderParticipantNode

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6717`
**Canonical date**: 2026-04-17 (git blame)
**Legacy heading**

```text
P347-BUGFIX + P347-NODEGENERAL: Fix and generalize CreateFinderParticipantNode
```

**Completed**: P347-BUGFIX (BUG-26041701) and P347-NODEGENERAL (IDEA-26041702)

### Summary

Fixed a bug in `CreateFinderParticipantNode` where `VultronActivity(type_="Add",
object_=participant.id_, ...)` used a bare string as `object_`, violating
MV-09-001 and causing `VultronOutboxObjectIntegrityError` after dehydration.

Simultaneously generalized the node to `CreateCaseParticipantNode(actor_id,
roles, report_id)`, removing the hard-coded finder/reporter coupling and
eliminating the runtime DataLayer offer lookup (the finder's actor ID is now
passed as a constructor argument from `SubmitReportReceivedUseCase`).

### Files Changed

- `vultron/core/behaviors/case/nodes.py` — replaced `CreateFinderParticipantNode`
  with `CreateCaseParticipantNode(actor_id, roles, report_id)`; removed unused
  `VultronActivity` import; added backward-compat alias; fixed object_ bug to use
  `AddParticipantToCaseActivity(object_=CaseParticipant)` with proper coercion
- `vultron/core/behaviors/case/receive_report_case_tree.py` — added
  `finder_actor_id: str` parameter to `create_receive_report_case_tree()`;
  updated `CreateCaseParticipantNode` invocation
- `vultron/core/use_cases/received/report.py` — pass `finder_actor_id=request.actor_id`
- `test/core/use_cases/received/test_report.py` — removed offer pre-storage
  (no longer needed); updated comments from `CreateFinderParticipantNode` to
  `CreateCaseParticipantNode`
- `test/core/behaviors/case/test_receive_report_case_tree.py` — added
  `finder_actor_id` fixture injection to all test functions
- `test/core/behaviors/report/test_validate_tree.py` — added `finder_actor_id`
  to `case` fixture
- `test/core/behaviors/case/test_bug_26040902_regression.py` — added
  `finder_actor_id=_finder_actor_id`
- `test/adapters/driving/fastapi/routers/test_trigger_report.py` — added
  `finder_actor_id=actor.id_`
- `test/adapters/driving/fastapi/test_trigger_services.py` — added
  `finder_actor_id=actor.id_`; restored `accepted_report` fixture

### Test Result

1619 passed, 12 skipped, 182 deselected, 5581 subtests passed
