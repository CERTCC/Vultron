---
title: "TECHDEBT-13b/c \u2014 Wire-boundary cleanup: _base.py and TYPE_CHECKING\
  \ imports"
type: implementation
timestamp: '2026-03-11T00:00:00+00:00'
source: LEGACY-2026-03-11-techdebt-13b-c-wire-boundary-cleanup-base-py-and
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1165
legacy_heading: "TECHDEBT-13b/c \u2014 Wire-boundary cleanup: _base.py and\
  \ TYPE_CHECKING imports (COMPLETE 2026-03-11)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-11'
---

## TECHDEBT-13b/c — Wire-boundary cleanup: _base.py and TYPE_CHECKING imports

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1165`
**Canonical date**: 2026-03-11 (git blame)
**Legacy heading**

```text
TECHDEBT-13b/c — Wire-boundary cleanup: _base.py and TYPE_CHECKING imports (COMPLETE 2026-03-11)
```

**Legacy heading dates**: 2026-03-11

**TECHDEBT-13b**: Updated `vultron/wire/as2/vocab/examples/_base.py` to remove
all adapter-layer imports. The module-level `DataLayer` annotation now imports
from `vultron.core.ports.activity_store`; `initialize_examples()` requires an
explicit `DataLayer` argument (removed `None` default, `get_datalayer()`
fallback, and `Record.from_obj()` usage). Objects are passed directly to
`datalayer.create()` since the `DataLayer` protocol accepts `BaseModel`.

**TECHDEBT-13c**: Updated `TYPE_CHECKING` guard imports in `vultron/types.py`
and `vultron/behavior_dispatcher.py` to reference
`vultron.core.ports.activity_store.DataLayer` directly instead of the
`vultron.api.v2.datalayer.abc` shim.

**Result**: 880 tests pass, 0 regressions. V-24 fully resolved.
