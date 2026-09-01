---
name: 2627-deferred-bugs-dl-read-case
description: Three pre-existing bugs found during code review of #2627 — test mocks stub dl.read when production calls dl.read_case
metadata:
  type: project
---

Three bugs discovered (not introduced) during code review of Issue #2627 PR.
All are pre-existing from the `read` → `read_case` migration.

- #2923 — test mocks stub `mock_dl.read` but production nodes call `dl.read_case`; regression guards silently dead (3 locations in embargo + suggest_actor tests)
- #2925 — `read_case(raise_on_missing=True)` silently returns `None` for non-VulnerabilityCase records
- #2926 — `ActorAlreadyParticipantNode` still calls `dl.read()` instead of `dl.read_case()`

**Why:** Found during code review of #2627 (ADR citation anchors). Pre-existing — none of the affected files were in the PR diff. Filed as Someday on the project board.

**How to apply:** When working in embargo lifecycle nodes, suggest_actor trees, or datalayer, check if these are still open and consider fixing in context.
