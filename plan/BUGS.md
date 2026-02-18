# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

## ✅ FIXED: Docker Compose PROJECT_NAME Variable Missing

**Status**: ✅ FIXED (2026-02-17)

**Problem**: The `docker-compose.yml` file references `${PROJECT_NAME}` for image naming, but the `.env` file only contained `COMPOSE_PROJECT_NAME=vultron`. This caused docker-compose to emit warnings about the missing variable and resulted in images with empty project name prefix (e.g., `-base:latest` instead of `vultron-base:latest`).

Additionally, when the health check was added to the `api-dev` service, it required `curl` to be installed in the base image. However, running containers were using old images built before `curl` was added, causing the health check to fail with "executable file not found in $PATH".

**Logs showing the bug**:
```
WARN[0000] The "PROJECT_NAME" variable is not set. Defaulting to a blank string.
```

**Root Cause**: Environment variable mismatch between `.env` (which had `COMPOSE_PROJECT_NAME`) and `docker-compose.yml` (which referenced `PROJECT_NAME`). Combined with stale Docker images that needed rebuilding after Dockerfile changes.

**Solution Implemented**:

1. **Added PROJECT_NAME to `.env` file**:
   - Added `PROJECT_NAME=vultron` alongside existing `COMPOSE_PROJECT_NAME=vultron`
   - Maintains backward compatibility while fixing the variable reference

2. **Added test to prevent regression**:
   - Created `test/docker/test_docker_compose_config.sh` to verify:
     - `.env` file exists
     - `PROJECT_NAME` is set in `.env`
     - `docker-compose config` produces no warnings about missing PROJECT_NAME
     - Image names are properly formed (vultron-*:latest)

**Tests Added**: Shell script test at `test/docker/test_docker_compose_config.sh`

**Test Results**: All 378 tests passing (2 xfail expected)

**Files Changed**:
- `docker/.env`: Added `PROJECT_NAME=vultron`
- `test/docker/test_docker_compose_config.sh`: New test script to verify configuration

**Verification**:
```bash
cd docker && docker-compose config  # No warnings
docker-compose build --no-cache base dependencies api-dev receive-report-demo
docker-compose up api-dev receive-report-demo  # All 3 demos complete successfully
```

---

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
