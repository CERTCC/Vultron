---
title: "TECHDEBT-32c \u2014 Remove get_datalayer fallback from wire/as2/rehydration.py"
type: implementation
date: '2026-03-24'
source: TECHDEBT-32c
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2914
legacy_heading: "TECHDEBT-32c \u2014 Remove get_datalayer fallback from wire/as2/rehydration.py"
date_source: git-blame
---

## TECHDEBT-32c — Remove get_datalayer fallback from wire/as2/rehydration.py

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2914`
**Canonical date**: 2026-03-24 (git blame)
**Legacy heading**

```text
TECHDEBT-32c — Remove get_datalayer fallback from wire/as2/rehydration.py
```

**Completed**: 2026-03-24

### What was done

Removed the adapter-layer import (`from vultron.adapters.driven.datalayer_tinydb
import get_datalayer`) from `vultron/wire/as2/rehydration.py`. The wire layer
must not import from a concrete adapter implementation.

- Made `dl: DataLayer` a required positional parameter in `rehydrate()`;
  removed the `None` default and the fallback `get_datalayer()` call.
- Updated three adapter-layer callers to pass `dl` explicitly:
  `vultron/adapters/driving/cli.py`,
  `vultron/adapters/driving/fastapi/routers/datalayer.py`,
  `vultron/adapters/driving/fastapi/inbox_handler.py`.
- Removed 25 legacy `monkeypatch.setattr(rehydration.get_datalayer, ...)` stubs
  from 6 test files under `test/core/use_cases/` — these were defensive patches
  for a fallback that no longer exists.
- Updated test mock in `test/api/v2/backend/test_inbox_handler.py` to accept
  `dl` keyword argument.

### Lessons learned

The "all production callers already pass `dl` explicitly" note in the plan was
incorrect — three adapter-layer callers were not passing `dl`. The fix required
updating callers in addition to removing the fallback. Always verify caller
state before relying on plan notes about external-facing APIs.

### Test results

985 passed, 5581 subtests passed.
