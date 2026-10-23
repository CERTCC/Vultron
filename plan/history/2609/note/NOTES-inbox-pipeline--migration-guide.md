---
source: NOTES-inbox-pipeline--migration-guide
timestamp: '2026-09-17T17:25:24.981815+00:00'
title: Migration Guide for Existing Tests
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) one-time migration completed
**Superseded by:** test/adapters/driving/fastapi/

---

## Migration Guide for Existing Tests

Existing mock-based tests in
`test/adapters/driving/fastapi/test_inbox_handler.py` remain valid for
fast unit coverage of `inbox_handler.py` internals. Do **not** delete them.

New routing-safety-net tests go in the separate
`test/adapters/driving/fastapi/test_inbox_pipeline.py` file. They
complement, not replace, the mock-based tests.

```text
test/adapters/driving/fastapi/
  test_inbox_handler.py       # existing — keep as-is
  test_inbox_pipeline.py      # new — routing safety net
  conftest.py                 # add test_pipeline fixture here
```
