---
source: ISSUE-570
timestamp: '2026-05-21T14:58:54.020252+00:00'
title: 'Demo CI: GitHub Actions integration workflow + demo runner hardening'
type: implementation
---

## Issue #570 — Demo CI: GitHub Actions integration workflow + demo runner hardening

Implemented all acceptance criteria from #570 to close the gap where pytest
tests pass while the live demo silently fails.

### Changes

**Demo runner hardening (DEMOCI-01):**

- Added `DemoFailureError` as a subclass of `VultronError` in `vultron/errors.py`
- Extended `demo_step` and `demo_check` in `vultron/demo/utils.py` to accumulate
  errors instead of re-raising; added `reset_demo_failures()` and
  `assert_demo_success()` helper pair
- HTTP 404 responses from `DataLayerClient.call()` are recorded in the failure
  accumulator with a specific URL context message
- `two_actor_demo.main()` now calls `reset_demo_failures()` at start and
  `assert_demo_success()` in a `try/finally` at end, ensuring non-zero exit on
  any demo step failure

**Compose / logging fixes (AC-9, AC-10):**

- All five actor services in `docker/docker-compose-multi-actor.yml` updated to
  use `VULTRON_SERVER__LOG_LEVEL=INFO` (replaces vestigial `LOG_LEVEL=INFO`)
- `ENV LOG_LEVEL=DEBUG` removed from the `api-dev` Dockerfile stage
- Makefile simplified: `integration-test-{multi-actor,three-actor,multi-vendor}`
  removed; single `make demo-2-test` target added

**GitHub Actions workflow (DEMOCI-02):**

- Created `.github/workflows/demo-integration.yml` as a standalone workflow
- Path-filtered PR trigger (`vultron/**`, `docker/**`, `integration_tests/**`,
  `pyproject.toml`, `uv.lock`) + `workflow_dispatch`
- Dependabot PRs skipped; 15-minute job timeout
- Docker layer caching; `--exit-code-from demo-runner` failure detection
- On failure: uploads combined + per-service logs as CI artifact
- `VULTRON_SERVER__LOG_LEVEL=DEBUG` set at CI runtime for full tracebacks
- Always-teardown step with `docker compose down -v`

**Tests:**

- `test/demo/test_demo_context_managers.py` updated to reflect
  accumulate-not-reraise behavior; new `TestDemoAccumulator` class with 7 tests
- `test/demo/test_two_actor_demo.py`: `test_raises_on_invalid_case` updated to
  verify accumulator instead of expecting exception propagation
- All 2660 tests pass (including full integration suite)

PR: [#591](https://github.com/CERTCC/Vultron/pull/591)
