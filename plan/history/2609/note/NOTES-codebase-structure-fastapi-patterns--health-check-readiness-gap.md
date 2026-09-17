---
source: NOTES-codebase-structure-fastapi-patterns--health-check-readiness-gap
timestamp: '2026-09-17T17:08:15.557758+00:00'
title: Health Check Readiness Gap
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) /ready implemented per OB-05-002
**Superseded by:** vultron/adapters/driving/fastapi/routers/health.py:35

---

## Health Check Readiness Gap

**Known gap**: The `/health/ready` endpoint in
`vultron/adapters/driving/fastapi/routers/health.py` currently returns
`{"status": "ok"}` unconditionally. It does **not** check DataLayer
connectivity as required by
`specs/observability.yaml` OB-05-002.

**When implementing readiness**: Add a DataLayer read probe (e.g., attempt a
simple `dl.list()` call) and return HTTP 503 if it fails.
