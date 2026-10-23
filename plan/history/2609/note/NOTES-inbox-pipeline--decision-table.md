---
source: NOTES-inbox-pipeline--decision-table
timestamp: '2026-09-17T17:25:23.858607+00:00'
title: Decision Table
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) build decisions for shipped class
**Superseded by:** vultron/adapters/driving/fastapi/inbox_pipeline.py

---

## Decision Table

| Question | Decision | Rationale |
|----------|----------|-----------|
| Which pipeline path to wrap? | Full `_process_inbox_item` path | Surfaces deferral and error-requeue — the untested behaviors listed in the RFC |
| Where should the class live? | `vultron/adapters/driving/fastapi/inbox_pipeline.py` | Co-located with `inbox_handler.py`; avoids a new layer |
| Return type of `process()`? | `VultronEvent \| None` | `None` = clean signal that dispatch did not occur (deferred or error) |
| Should `_DISPATCHER` global change? | No — pipeline is additive | `InboxPipeline` is a parallel path; production lifespan wiring is unchanged |
| Factory function vs. fixture? | Both | Module-level `build_test_pipeline()` + `conftest.py` pytest fixture |
| ADR needed? | No | Purely additive; no evaluated alternative was rejected (MS-11-005) |
| Spec ID prefix? | `IBP` in `specs/inbox-pipeline.yaml` | Self-contained spec for the pipeline contract |
| Test coverage scope? | One routing-safety-net test per semantic domain | ~7 tests catch registration gaps without full enum-value matrix |

---
