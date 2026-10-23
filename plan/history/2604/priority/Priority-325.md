---
source: Priority-325
timestamp: '2026-04-14T00:00:00+00:00'
title: 'Priority 325: TinyDB → SQLModel/SQLite Datalayer Migration'
type: priority
---

Replace the TinyDB persistence backend with a SQLModel/SQLite adapter.
TinyDB's O(n) I/O cost (whole-file rewrite on every operation) was measured
concretely in BUG-2026041001: the test suite grew from ~13 s to 15+ minutes
as test coverage expanded. The fix required a `pytest_configure` monkey-patch
to force `MemoryStorage` globally — accidental complexity paid entirely to
work around a TinyDB limitation, not to test any application behavior.

**Approach**: Single-table polymorphic SQLModel storage model
(`VultronObjectRecord`) defined entirely in the adapter layer. Domain models
(Pydantic) are unchanged. SQLModel is isolated to the adapter.
Test isolation via `sqlite:///:memory:` replaces the monkey-patch.

Tasks: DL-SQLITE-ADR, DL-SQLITE-1, DL-SQLITE-2, DL-SQLITE-3, DL-SQLITE-4,
DL-SQLITE-5. All must complete before D5-7-HUMAN (Priority 330).

IDEA-26040901 (TinyDB table consolidation) is superseded by this migration.
IDEA-26040902 is the primary driver.
