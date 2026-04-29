---
title: "DEMO-4 \u2014 Unified Demo CLI"
type: implementation
date: '2026-02-27'
source: DEMO-4
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 167
legacy_heading: "Phase DEMO-4 \u2014 Unified Demo CLI (COMPLETE 2026-02-27)"
date_source: git-blame
legacy_heading_dates:
- '2026-02-27'
---

## DEMO-4 — Unified Demo CLI

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:167`
**Canonical date**: 2026-02-27 (git blame)
**Legacy heading**

```text
Phase DEMO-4 — Unified Demo CLI (COMPLETE 2026-02-27)
```

**Legacy heading dates**: 2026-02-27

All 19 tasks completed. Key achievements:

- **DEMO-4.1–4.2**: Shared utilities (`demo_step`, `demo_check`, HTTP helpers,
  `DataLayerClient`, `demo_environment` context manager) extracted to
  `vultron/demo/utils.py`; all demo scripts updated to import from there
- **DEMO-4.3**: All 12 `*_demo.py` scripts moved from `vultron/scripts/` to
  `vultron/demo/`; test imports updated from `test/scripts/` to `test/demo/`
- **DEMO-4.4**: `demo_environment(client)` context manager added to
  `vultron/demo/utils.py`; guaranteed teardown (setup + `reset_datalayer` +
  `clear_all_actor_ios`) even on exception; all demo scripts updated
- **DEMO-4.5–4.6**: `vultron/demo/cli.py` — `click`-based CLI with
  sub-commands for all 12 demos plus `all`; `--debug` and `--log-file`
  options on `main` group; `vultron-demo` entry point in `pyproject.toml`
- **DEMO-4.7–4.8**: Unified `demo` Docker service in
  `docker/docker-compose.yml` with `condition: service_healthy` on `api-dev`;
  individual per-demo services removed
- **DEMO-4.9–4.11**: `test/demo/test_cli.py`; demo tests migrated to
  `test/demo/`; `conftest.py` sets `DEFAULT_WAIT_SECONDS=0.0` eliminating
  all `time.sleep` calls in tests; `_helpers.py` `make_testclient_call`
  factory; demo suite ~10× faster
- **DEMO-4.12–4.14**: `integration_tests/demo/` with integration test script
  and `README.md`; `make integration-test` Makefile target
- **DEMO-4.15–4.19**: `vultron/demo/README.md`; updated
  `docs/howto/activitypub/activities/*.md`; two demo tutorials in
  `docs/tutorials/`; docstrings and `docs/reference/code/demo/*.md`
