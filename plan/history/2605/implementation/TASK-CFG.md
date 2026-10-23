---
source: TASK-CFG
timestamp: '2026-05-04T14:52:34.275847+00:00'
title: Unified Configuration System (TASK-CFG)
type: implementation
---

Implemented TASK-CFG: Unified Configuration System.

## Changes

### New files

- `vultron/config.py`: `AppConfig(BaseSettings)` with nested `ServerConfig` and
  `DatabaseConfig` (plain `BaseModel`), `RunMode(StrEnum)`, `YamlConfigSource`,
  `get_config()`, and `reload_config()`. Env prefix `VULTRON_`, nested delimiter `__`.
- `test/test_config.py`: 22 tests covering CFG-06 requirements (defaults, env
  overrides, YAML loading, precedence, error handling).

### Modified files

- `vultron/adapters/utils.py`: Replaced `os.environ.get("VULTRON_BASE_URL", ...)`
  with `get_config().server.base_url`. Default changed from `https://demo.vultron.local/`
  to `http://localhost:7999` per CFG-04-003.
- `vultron/adapters/driven/datalayer_sqlite.py`: Removed module-level
  `_DEFAULT_DB_URL` constant; `get_datalayer()` now lazily reads
  `get_config().database.db_url`.
- `vultron/adapters/driving/fastapi/app.py`: Replaced `os.environ.get("LOG_LEVEL")`
  with `get_config().server.log_level`.
- `test/conftest.py`: `VULTRON_DB_URL` → `VULTRON_DATABASE__DB_URL`.
- Various test files updated to use new nested env var names + `_config_cache = None`
  fixture teardown pattern.

### Dependencies

- Added `pydantic-settings==2.14.0` (+ transitive `python-dotenv==1.2.2`).

## Deferred

- CFG.2 (SeedConfig BaseSettings refactor): SHOULD, not MUST. Existing
  `seed_config.py` already satisfies CFG-05-002 and CFG-05-003.
