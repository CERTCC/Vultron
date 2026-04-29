---
title: "VCR-B \u2014 Move FastAPI adapter to vultron/adapters/driving/fastapi/\
  \ (2026-03-18)"
type: implementation
date: '2026-03-18'
source: VCR-B
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2038
legacy_heading: "VCR-B \u2014 Move FastAPI adapter to vultron/adapters/driving/fastapi/\
  \ (2026-03-18)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-18'
---

## VCR-B — Move FastAPI adapter to vultron/adapters/driving/fastapi/ (2026-03-18)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2038`
**Canonical date**: 2026-03-18 (git blame)
**Legacy heading**

```text
VCR-B — Move FastAPI adapter to vultron/adapters/driving/fastapi/ (2026-03-18)
```

**Legacy heading dates**: 2026-03-18

**Task**: VCR-003/004/007/008/009/017/018 (Batch VCR-B)

### What was done

Created `vultron/adapters/driving/fastapi/` subpackage consolidating all
FastAPI-specific code from the former `vultron/api/v2/` location:

- `vultron/api/v2/routers/` → `vultron/adapters/driving/fastapi/routers/`
- `vultron/api/v2/app.py` → `vultron/adapters/driving/fastapi/app.py`
- `vultron/api/main.py` → `vultron/adapters/driving/fastapi/main.py`
- `vultron/api/v2/backend/inbox_handler.py` → `vultron/adapters/driving/fastapi/inbox_handler.py`
  (replaced the stub at `vultron/adapters/driving/http_inbox.py`)
- `vultron/api/v2/backend/outbox_handler.py` → `vultron/adapters/driving/fastapi/outbox_handler.py`
- `vultron/api/v2/errors.py` → `vultron/adapters/driving/fastapi/errors.py`
- `vultron/api/v2/backend/helpers.py` → `vultron/adapters/driving/fastapi/helpers.py`

External callers updated: `vultron/adapters/driving/cli.py`, `docker/Dockerfile`,
9 test files. No backward-compat shims left behind.

Remaining in `vultron/api/`: `actor_io.py` (VCR-014), `trigger_services/` (VCR-D),
`datalayer/` stub package. These are handled by separate tasks.

### Test results

981 passed, 5581 subtests, 5 warnings.
