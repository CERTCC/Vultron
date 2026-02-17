# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

## ✅ FIXED: Docker Container Startup Race Condition

**Status**: ✅ FIXED (2026-02-17)

**Problem**: The `receive-report-demo` container was failing to connect to the `api-dev` service when both were started with `docker-compose up`. The demo script only checked once for server availability with a 2-second timeout, but the API server takes several seconds to fully start after the container starts.

**Logs showing the bug**:
```
api-dev-1              | INFO:     Started reloader process [9] using StatReload
receive-report-demo-1  | 2026-02-17 21:29:35,724 ERROR Cannot connect to: http://api-dev:7999/api/v2
receive-report-demo-1 exited with code 1
api-dev-1              | INFO:     Started server process [11]
api-dev-1              | INFO:     Application startup complete.
```

**Root Cause**: Classic Docker race condition - `depends_on: service_started` only waits for the container to start, not for the application inside to be ready.

**Solution Implemented**:

1. **Added retry logic to `check_server_availability()`** in `vultron/scripts/receive_report_demo.py`:
   - Added `max_retries` parameter (default: 30 attempts)
   - Added `retry_delay` parameter (default: 1.0 seconds)
   - Logs each retry attempt at DEBUG level
   - Returns True on first successful check, False after exhausting retries

2. **Added Docker health check** to `api-dev` service in `docker-compose.yml`:
   - Uses `curl` to check `/api/v2/actors/` endpoint
   - Checks every 2 seconds with 15 retries (30 seconds total)
   - 5-second start period before first check

3. **Updated `receive-report-demo` dependency** in `docker-compose.yml`:
   - Changed from `condition: service_started` to `condition: service_healthy`
   - Now waits for API server to pass health check before starting

4. **Added `curl` to Docker base image** in `Dockerfile`:
   - Required for health check to work

**Tests Added**: `test/scripts/test_health_check_retry.py` with 5 test cases:
- Immediate success
- Permanent failure after retries
- Success after initial failures
- Retry attempt logging
- Respects max_retries limit

**Test Results**: All 91 tests passing (2 xfail expected)

**Files Changed**:
- `vultron/scripts/receive_report_demo.py`: Added retry logic
- `docker/docker-compose.yml`: Added health check and updated dependency
- `docker/Dockerfile`: Added curl to base image
- `test/scripts/test_health_check_retry.py`: New test file
