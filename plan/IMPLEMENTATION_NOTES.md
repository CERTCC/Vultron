# Implementation Notes

**Last Updated**: 2026-02-17 (Gap analysis via PLAN_prompt.md)

---

## Critical Findings from Gap Analysis

### 1. Test Infrastructure Issue (CRITICAL - Phase 0.5)

**Problem**: 11 router tests failing due to fixture isolation bug.

**Root Cause**: `client_actors` and `client_datalayer` fixtures in `test/api/v2/routers/conftest.py` create fresh FastAPI apps that instantiate their own data layer via `get_datalayer()` with default path `"mydb.json"`. Meanwhile, test data created by the `created_actors` fixture uses a separate `datalayer` fixture (from `test/api/v2/conftest.py`) with `db_path=None` for in-memory storage.

**Result**: Tests write to data layer instance A, routers read from data layer instance B (fresh, empty).

**Solution**: Override `get_datalayer` dependency in test client fixtures.

**Impact**: Blocks all router testing. Must fix before proceeding with other test work.

---

### 2. Handler Implementation Status

**Completed**: 7 of 36 handlers (19%)
- Report handlers: 6 complete (create, submit, validate, invalidate, ack, close)
- Special handlers: 1 complete (unknown)

**Remaining Stubs**: 24 handlers (67%) across 6 categories
- Case management: 8 handlers
- Participant management: 6 handlers  
- Embargo management: 6 handlers
- Notes & statuses: 5 handlers

**What's Missing**: All business logic (rehydration, validation, persistence, logging at INFO level).

---

### 3. Demo Script Status

**Status**: ✅ COMPLETE (as of 2026-02-13)

Three working demos: validate, invalidate, invalidate+close

---

### 4. Test Suite Health

**Overall Status**: 361 passing, 11 failing, 2 xfailed (98% pass rate)

**Failing Tests (11)**: All due to fixture isolation issue

---

### 5. Recommendations

**Immediate**: Fix test fixture isolation (Phase 0.5)

**Short Term**: Decide direction (expand demos vs production readiness)

**Medium Term**: Coverage measurement, remaining handlers, integration tests

**Long Term**: Response generation, outbox processing, auth
