---
source: NOTES-inbox-pipeline--routing-safety-net-test
timestamp: '2026-09-17T17:25:24.697645+00:00'
title: Routing-Safety-Net Test Pattern
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** test/adapters/driving/fastapi/test_inbox_pipeline.py

---

## Routing-Safety-Net Test Pattern

One test per semantic domain. Each test:

1. Constructs the required domain objects with full URIs
2. Saves them to the in-memory DataLayer
3. Calls `pipeline.process(activity.id_)`
4. Asserts `event.semantic_type == MessageSemantics.<EXPECTED>`
5. Asserts the expected DataLayer side effect occurred

```python
def test_create_report_routes_correctly(test_pipeline):
    pipeline, dl = test_pipeline

    report = VulnerabilityReport(
        id_="https://example.org/reports/r-1", ...
    )
    activity = rm_create_report_activity(
        report=report,
        actor="https://example.org/actors/reporter",
        to=["https://example.org/actors/coordinator"],
    )
    dl.save(report)
    dl.save(activity)

    event = pipeline.process(activity.id_)

    assert event is not None
    assert event.semantic_type == MessageSemantics.CREATE_REPORT
    # assert expected DataLayer side effect
    assert dl.read(report.id_) is not None
```

### Semantic domains and representative test cases

| Domain | Representative semantic type | Key side effect to assert |
|--------|------------------------------|--------------------------|
| Report | `CREATE_REPORT` | Report saved in DataLayer |
| Case | `ANNOUNCE_VULNERABILITY_CASE` | Case saved or deferred |
| Embargo | `OFFER_EMBARGO` | Embargo offer recorded |
| Note | `CREATE_NOTE` | Note attached to case |
| Actor | `ANNOUNCE_ACTOR` | Actor profile saved |
| Status | `ANNOUNCE_CASE_STATUS` | Case status updated |
| Sync | `ANNOUNCE_LOG_ENTRY` | Log entry persisted |

### Deferral path test pattern

```python
def test_activity_with_unknown_case_is_deferred(test_pipeline):
    pipeline, dl = test_pipeline
    # activity referencing a case not yet in dl
    ...
    result = pipeline.process(activity.id_)

    assert result is None  # not dispatched
    # activity ID appears in pending-case inbox
    pending = dl.get("pending_case_inbox", ...)
    assert activity.id_ in pending
```

---
