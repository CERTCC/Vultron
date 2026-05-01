---
title: "D5-1-G1 and D5-1-G6 \u2014 Info Endpoint and Inbox URL Derivation\
  \ Test (2026-03-31)"
type: implementation
timestamp: '2026-03-31T00:00:00+00:00'
source: LEGACY-2026-03-31-d5-1-g1-and-d5-1-g6-info-endpoint-and-inbox-url
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3953
legacy_heading: "D5-1-G1 and D5-1-G6 \u2014 Info Endpoint and Inbox URL Derivation\
  \ Test (2026-03-31)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-31'
---

## D5-1-G1 and D5-1-G6 — Info Endpoint and Inbox URL Derivation Test (2026-03-31)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3953`
**Canonical date**: 2026-03-31 (git blame)
**Legacy heading**

```text
D5-1-G1 and D5-1-G6 — Info Endpoint and Inbox URL Derivation Test (2026-03-31)
```

**Legacy heading dates**: 2026-03-31

### D5-1-G1 — VULTRON_BASE_URL Exposure via Info Endpoint

**Task**: Add a `GET /info` endpoint returning the configured `VULTRON_BASE_URL`
and the list of actor IDs registered in the shared DataLayer.

**What was done**:

- Created `vultron/adapters/driving/fastapi/routers/info.py` with a `GET /info`
  endpoint that returns `{"base_url": BASE_URL, "actors": [list of actor IDs]}`.
  Queries all actor table types ("Actor", "Application", "Group", "Organization",
  "Person", "Service") from the shared DataLayer to build the actor list.
- Registered the new `info.router` in `vultron/adapters/driving/fastapi/routers/v2_router.py`.
- Added `test/adapters/driving/fastapi/routers/test_info.py` with 5 tests
  covering: 200 response, `base_url` and `actors` fields present, empty actors
  list when no actors seeded, and actor IDs appearing in response after seeding.
- Confirmed `/health/ready` DataLayer connectivity check (OB-05-002) was already
  implemented via `dl.ping()` — no additional work needed there.

### D5-1-G6 — Inbox URL Derivation Integration Test

**Task**: Verify that `DeliveryQueueAdapter`'s inbox URL derivation formula
(`{actor_id}/inbox/`) is consistent with the FastAPI actors router.

**What was done**:

- Created `test/adapters/driven/test_delivery_inbox_url.py` with 6 tests:
  - Unit tests verifying the derivation formula appends `/inbox/`, normalises
    trailing slashes, and preserves the actor UUID.
  - Integration test that creates an actor with a Docker-style full URI ID
    (`http://finder:7999/api/v2/actors/{uuid}`), derives the inbox URL, strips
    the `/api/v2` prefix to get the app_v2-relative path, and POSTs to the
    FastAPI actors router, asserting 202 Accepted (not 404).
  - Path shape test confirming the path relative to app_v2 is `/actors/{uuid}/inbox/`.
- **No bugs found**: derivation logic is already correct; test serves as a
  regression guard for D5-2 work.

**Validation**:

- All 4 linters pass: `black`, `flake8`, `mypy`, `pyright` — 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1132 passed, 5581 subtests passed`
