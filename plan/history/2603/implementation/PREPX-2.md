---
title: "PREPX-2 \u2014 Remove handlers shim layer (2026-03-18)"
type: implementation
date: '2026-03-18'
source: PREPX-2
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1894
legacy_heading: "PREPX-2 \u2014 Remove handlers shim layer (2026-03-18)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-18'
---

## PREPX-2 — Remove handlers shim layer (2026-03-18)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1894`
**Canonical date**: 2026-03-18 (git blame)
**Legacy heading**

```text
PREPX-2 — Remove handlers shim layer (2026-03-18)
```

**Legacy heading dates**: 2026-03-18

Deleted the backward-compatibility shim layer:

- `vultron/api/v2/backend/handlers/__init__.py` (re-exported all 38 use cases
  as thin wrapper functions with `_unwrap` helper)
- `vultron/api/v2/backend/handlers/_shim.py` (no-op `verify_semantics` decorator)

Updated two test files to call use-case classes directly with `VultronEvent`
objects instead of going through the shim:

- `test/api/v2/backend/test_handlers.py`: removed `DispatchEvent` usage,
  `_make_dispatchable()` helper, and obsolete shim test classes
  (`TestVerifySemanticsDecorator`, `TestHandlerDecoratorPresence`); updated all
  `handlers.foo(dispatchable, dl)` calls to `FooReceivedUseCase(dl, event).execute()`.
- `test/api/test_reporting_workflow.py`: replaced handler-based `_call_handler`
  helper with `_call_use_case`; moved `TinyDbDataLayer` import into the `dl`
  fixture to avoid a circular-import startup issue.

VCR-006 (delete `handler_map.py` shim) is now unblocked.
PREPX-3 (remove `DispatchEvent` and `InboundPayload` aliases) is now unblocked.

### Test results

961 passed, 5581 subtests, 5 warnings (5 fewer due to removed shim-specific tests).
