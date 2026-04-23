# Configuration Management Specification

## Overview

This specification defines requirements for unified, structured application
configuration in Vultron. Configuration MUST use YAML files (for human
readability) backed by Pydantic-based models (for type safety and schema
clarity), loaded via `pydantic-settings` with environment variable override
support.

**Source**: IDEA-260402-01, design session 2026-04-23
**Note**: Applies to the `AppConfig` production config and to the refactored
`SeedConfig` demo/seed config. Demo scenario actor URLs (finder, vendor, etc.)
are out of scope for `AppConfig`.

---

## Module Placement and Config API

- `CFG-01-001` The application MUST provide a top-level neutral module
  `vultron/config.py` containing `AppConfig`, `get_config()`, and
  `reload_config()`.
- `CFG-01-002` `get_config()` MUST return a cached `AppConfig` instance —
  loaded once on first call, cached for all subsequent calls.
- `CFG-01-003` `reload_config()` MUST clear the cached instance so the next
  `get_config()` call re-reads configuration from the file and environment.
- `CFG-01-004` All code that previously called `os.environ.get()` for Vultron
  application settings MUST be updated to call `get_config()` instead.
- `CFG-01-005` `AppConfig` MUST be injectable in FastAPI routers via
  `Depends(get_config)`.
- `CFG-01-006` `vultron/config.py` MUST NOT import from adapter-layer or
  FastAPI modules; it is a neutral shared module usable by all layers.
  - CFG-01-006 refines ARCH-05-001 (core and neutral modules have no
    adapter-layer imports)

---

## Config File Format and Loading

- `CFG-02-001` The application MUST support loading configuration from a YAML
  file. The default path MUST be `config.yaml` in the project root (current
  working directory at startup).
- `CFG-02-002` The default config file path MUST be overridable via the
  `VULTRON_CONFIG` environment variable.
- `CFG-02-003` The application MUST use `pydantic-settings` (`BaseSettings`)
  with a custom YAML settings source to implement config loading.
- `CFG-02-004` Config loading precedence (lowest to highest) MUST be:
  YAML file < environment variables. Environment variable values MUST override
  YAML values for the same field.
- `CFG-02-005` The application MUST start successfully with no config file and
  no relevant environment variables set; all fields have sensible defaults.
- `CFG-02-006` If `VULTRON_CONFIG` is set and points to a non-existent file,
  the application MUST raise a descriptive error at startup (MUST NOT silently
  ignore a missing explicit config path).
- `CFG-02-007` If no config file exists at the default path and `VULTRON_CONFIG`
  is unset, the application MUST start using defaults only with no error.

---

## Environment Variable Naming

- `CFG-03-001` All Vultron application environment variables MUST use the
  `VULTRON_` prefix.
- `CFG-03-002` Nested config section fields MUST use double-underscore (`__`)
  as the hierarchy separator, following `pydantic-settings` nested-model
  conventions (e.g., `VULTRON_SERVER__BASE_URL`,
  `VULTRON_DATABASE__DB_URL`).
- `CFG-03-003` The following legacy environment variable names MUST be removed
  from all source files and replaced with their normalized equivalents:
  - `LOG_LEVEL` → `VULTRON_SERVER__LOG_LEVEL`
  - `VULTRON_BASE_URL` → `VULTRON_SERVER__BASE_URL`
  - `VULTRON_DB_URL` → `VULTRON_DATABASE__DB_URL`

---

## AppConfig Structure

- `CFG-04-001` `AppConfig` MUST have a `server` sub-section (a nested
  `ServerConfig` model) containing at minimum: `base_url` (str) and
  `log_level` (str).
- `CFG-04-002` `AppConfig` MUST have a `database` sub-section (a nested
  `DatabaseConfig` model) containing at minimum: `db_url` (str).
- `CFG-04-003` `ServerConfig.base_url` MUST default to
  `"http://localhost:7999"`.
- `CFG-04-004` `ServerConfig.log_level` MUST default to `"INFO"` and MUST
  be validated as one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
  (case-insensitive on input; stored upper-case).
- `CFG-04-005` `DatabaseConfig.db_url` MUST default to
  `"sqlite:///vultron.db"`.
- `CFG-04-006` Field validators MUST enforce per-field constraints (URL
  format, valid log level name) but MUST NOT implement cross-field business
  rules.
- `CFG-04-007` `AppConfig` MUST NOT include seed actor or demo scenario
  configuration; those belong in `SeedConfig`.

---

## SeedConfig Alignment

- `CFG-05-001` `SeedConfig` (in `vultron/demo/seed_config.py`) SHOULD be
  refactored to use `pydantic-settings` `BaseSettings` for consistency with
  `AppConfig`.
- `CFG-05-002` `SeedConfig` MUST remain a separate class and file from
  `AppConfig`; it is demo/seed tooling, not production config.
- `CFG-05-003` `SeedConfig` env var names MUST use the `VULTRON_` prefix
  (e.g., `VULTRON_ACTOR_NAME`, `VULTRON_ACTOR_TYPE`, `VULTRON_ACTOR_ID`,
  `VULTRON_SEED_CONFIG`).
  - Note: these names already exist; CFG-05-003 confirms they are retained
    and do not gain a `__`-separated section prefix since `SeedConfig` is
    a flat (non-nested) model.

---

## Testing

- `CFG-06-001` Config loading MUST be testable using `pytest`'s
  `monkeypatch.setenv()` to inject environment variable overrides without
  modifying the process environment permanently.
- `CFG-06-002` Config loading MUST be testable using `pytest`'s `tmp_path`
  fixture to supply a temporary YAML config file.
- `CFG-06-003` Test fixtures MUST call `reload_config()` in teardown (or via
  an `autouse` fixture) to clear the cached instance between test cases.
- `CFG-06-004` Tests MUST verify that environment variables override YAML
  values for the same field.
- `CFG-06-005` Tests MUST verify that the application starts successfully with
  all defaults (no file, no env vars set).
