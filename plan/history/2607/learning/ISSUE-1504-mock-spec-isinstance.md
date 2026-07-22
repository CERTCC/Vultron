---
title: MagicMock requires spec= when code uses isinstance() guards
type: learning
timestamp: "2026-07-20T00:00:00+00:00"
source: ISSUE-1504
---

When migrating from duck-typing guards (TypeGuard helpers that use `getattr`)
to `isinstance()` checks, test mocks using bare `MagicMock()` break silently:
the isinstance check returns False and the test hits the wrong branch.

Fix: use `MagicMock(spec=ConcreteClass)` so `isinstance(mock, ConcreteClass)`
returns True. This applies to every test that:

1. Creates a mock case, participant, or ledger entry, AND
2. Passes it through code that now uses `isinstance(x, VulnerabilityCase)` etc.

Symptom: test passes but verifies the wrong code path (e.g., "case not found"
instead of the intended ValueError branch).

**Promoted**: 2026-07-22 — captured in `test/AGENTS.md`.
Docs PR: TBD (fill in after PR is opened).
