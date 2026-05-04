---
title: Configuration Management — Implementation Notes
status: active
description: Design decisions for YAML-backed Pydantic configuration loading in Vultron.
related_specs:
  - specs/configuration.yaml
relevant_packages:
  - fastapi
  - pydantic
  - yaml
  - vultron/config
  - vultron/adapters
  - vultron/core
---

# Configuration Management — Implementation Notes

## Background

IDEA-260402-01 (design session 2026-04-23) established that Vultron config
files MUST use YAML for readability and MUST be loaded into Pydantic-backed
structured objects for type safety. This note captures the design decisions
and implementation guidance for `vultron/config.py` and the aligned
`SeedConfig` refactor.

See `specs/configuration.yaml` for the formal requirements (CFG-01 through
CFG-06).

---

## Design Decisions Summary

| Question | Decision | Rationale |
|----------|----------|-----------|
| Scope | All app config unified | Replace scattered `os.environ.get()` calls |
| Config file name | `config.yaml` at project root | Simple; overridable via `VULTRON_CONFIG` |
| Precedence | Env vars override YAML | 12-factor app convention |
| Implementation | `pydantic-settings` `BaseSettings` | Native env-var support, custom sources |
| Sections | `server` + `database` only | Production config; seed/demo stay separate |
| Loading API | `get_config()` factory + `reload_config()` | Mirrors `get_datalayer()` pattern |
| Env var naming | `VULTRON_` prefix + `__` nesting | Clean break; no backward compat needed |
| Defaults | All fields have defaults | Zero-config startup |
| Validation | Per-field only | Keep loading fast and simple |
| FastAPI | `Depends(get_config)` + direct calls | Consistent with DataLayer injection |

---

## Module Structure

```text
vultron/
  config.py          ← AppConfig, ServerConfig, DatabaseConfig,
                        get_config(), reload_config()
  demo/
    seed_config.py   ← SeedConfig (separate; refactored to BaseSettings)
```

`vultron/config.py` is a **neutral module** — it MUST NOT import from
`vultron/adapters/` or `vultron/wire/` or FastAPI. It sits alongside
`vultron/errors.py` and `vultron/enums.py` as a shared-access layer.

---

## Implementation Pattern

### AppConfig with pydantic-settings

```python
# vultron/config.py
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal, Any

import yaml
from pydantic import field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

logger = logging.getLogger(__name__)

LogLevelName = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class YamlConfigSource(PydanticBaseSettingsSource):
    """Custom pydantic-settings source that reads from a YAML file."""

    def __call__(self) -> dict[str, Any]:
        import os
        path = os.environ.get("VULTRON_CONFIG", "config.yaml")
        p = Path(path)
        if os.environ.get("VULTRON_CONFIG") and not p.exists():
            raise FileNotFoundError(
                f"VULTRON_CONFIG points to non-existent file: {path}"
            )
        if not p.exists():
            return {}
        with p.open() as fh:
            return yaml.safe_load(fh) or {}

    def get_fields_value(self, field_name: str, field_info):
        ...  # not called directly; __call__ returns the full dict


class ServerConfig(BaseSettings):
    base_url: str = "http://localhost:7999"
    log_level: LogLevelName = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        return v.upper()

    model_config = {"env_prefix": "VULTRON_SERVER__"}


class DatabaseConfig(BaseSettings):
    db_url: str = "sqlite:///vultron.db"

    model_config = {"env_prefix": "VULTRON_DATABASE__"}


class AppConfig(BaseSettings):
    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()

    model_config = {
        "env_prefix": "VULTRON_",
        "env_nested_delimiter": "__",
    }

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        secrets_settings,
    ):
        # Precedence (first = highest): env vars > YAML.
        # In pydantic-settings 2.x the FIRST source in the returned tuple wins.
        # Putting env_settings first ensures environment variables override YAML.
        return (
            env_settings,
            YamlConfigSource(settings_cls),
        )


_config_cache: AppConfig | None = None


def get_config() -> AppConfig:
    global _config_cache
    if _config_cache is None:
        _config_cache = AppConfig()
    return _config_cache


def reload_config() -> AppConfig:
    global _config_cache
    _config_cache = None
    return get_config()
```

> **Note on nested env vars**: `pydantic-settings` with
> `env_nested_delimiter="__"` maps `VULTRON_SERVER__BASE_URL` to
> `AppConfig.server.base_url` automatically. The `ServerConfig` and
> `DatabaseConfig` sub-objects are constructed by pydantic-settings using
> the nested delimiter.

---

## YAML File Format

The canonical `config.yaml` schema:

```yaml
# config.yaml — Vultron application configuration
# All fields are optional; omit to use defaults.

server:
  base_url: "http://localhost:7999"
  log_level: "INFO"

database:
  db_url: "sqlite:///vultron.db"
```

---

## Environment Variable Reference

| Env var | Maps to | Default |
|---------|---------|---------|
| `VULTRON_CONFIG` | path to config.yaml | `config.yaml` |
| `VULTRON_SERVER__BASE_URL` | `server.base_url` | `http://localhost:7999` |
| `VULTRON_SERVER__LOG_LEVEL` | `server.log_level` | `INFO` |
| `VULTRON_DATABASE__DB_URL` | `database.db_url` | `sqlite:///vultron.db` |

### Legacy env var migration

The following env var names were used in the codebase before this design
was adopted. They MUST be replaced everywhere:

| Old name | New name |
|----------|----------|
| `LOG_LEVEL` | `VULTRON_SERVER__LOG_LEVEL` |
| `VULTRON_BASE_URL` | `VULTRON_SERVER__BASE_URL` |
| `VULTRON_DB_URL` | `VULTRON_DATABASE__DB_URL` |

`SeedConfig`-specific env vars (`VULTRON_ACTOR_NAME`, `VULTRON_ACTOR_TYPE`,
`VULTRON_ACTOR_ID`, `VULTRON_SEED_CONFIG`) are unchanged.

---

## Call-site Migration

### Before (scattered os.environ.get)

```python
# vultron/adapters/utils.py
BASE_URL = os.environ.get("VULTRON_BASE_URL", "https://demo.vultron.local/")

# vultron/adapters/driven/datalayer_sqlite.py
_DEFAULT_DB_URL = os.environ.get("VULTRON_DB_URL", "sqlite:///vultron.db")

# vultron/adapters/driving/fastapi/app.py
log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
```

### After (unified get_config())

```python
from vultron.config import get_config

# vultron/adapters/utils.py
BASE_URL = get_config().server.base_url

# vultron/adapters/driven/datalayer_sqlite.py
_DEFAULT_DB_URL = get_config().database.db_url

# vultron/adapters/driving/fastapi/app.py
log_level_name = get_config().server.log_level
```

### FastAPI Depends injection

```python
from fastapi import Depends
from vultron.config import AppConfig, get_config

@router.get("/info")
async def info(config: AppConfig = Depends(get_config)):
    return {"base_url": config.server.base_url}
```

---

## Testing Pattern

```python
# test/test_config.py
import pytest
import vultron.config as _cfg_module
from vultron.config import get_config, reload_config


@pytest.fixture(autouse=True)
def reset_config():
    yield
    # Set the cache to None directly rather than calling reload_config().
    # reload_config() fires the cache reset BEFORE pytest's monkeypatch reverts
    # env-var changes, locking in the test's env state for the reload.
    # Nulling the cache directly lets the NEXT test's get_config() call reload
    # with a clean env provided by the session-level conftest.py.
    _cfg_module._config_cache = None


def test_defaults(tmp_path):
    cfg = get_config()
    assert cfg.server.base_url == "http://localhost:7999"
    assert cfg.server.log_level == "INFO"
    assert cfg.database.db_url == "sqlite:///vultron.db"


def test_env_override(monkeypatch):
    monkeypatch.setenv("VULTRON_SERVER__BASE_URL", "http://myserver:8080")
    reload_config()
    assert get_config().server.base_url == "http://myserver:8080"


def test_yaml_file(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("server:\n  log_level: DEBUG\n")
    monkeypatch.setenv("VULTRON_CONFIG", str(cfg_file))
    reload_config()
    assert get_config().server.log_level == "DEBUG"


def test_env_overrides_yaml(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("server:\n  log_level: DEBUG\n")
    monkeypatch.setenv("VULTRON_CONFIG", str(cfg_file))
    monkeypatch.setenv("VULTRON_SERVER__LOG_LEVEL", "ERROR")
    reload_config()
    assert get_config().server.log_level == "ERROR"
```

---

## SeedConfig Refactoring Notes

`SeedConfig` in `vultron/demo/seed_config.py` already uses the
`yaml.safe_load()` + `model_validate()` pattern. The refactor to
`pydantic-settings` `BaseSettings` makes loading consistent with
`AppConfig`. Key changes:

- Subclass `BaseSettings` instead of `BaseModel`
- Set `model_config = {"env_prefix": "VULTRON_", ...}` with appropriate
  field aliases matching existing env var names
- Remove `from_env()` and `from_file()` classmethods; `BaseSettings`
  handles source merging automatically
- Keep `load()` as a thin wrapper for the `VULTRON_SEED_CONFIG` path
  override (or replace with a `YamlConfigSource` on `SeedConfig`)
- `LocalActorConfig` and `PeerActorConfig` stay as plain `BaseModel`
  since they are sub-models, not top-level settings

---

## Relation to Existing Code

### What this does NOT change

- `SeedConfig`'s YAML format and field names (backward-compatible schema)
- Docker seed-config YAML files in `docker/seed-configs/`
- Demo scenario actor URL constants (those live in demo scripts, not
  AppConfig)
- The `.env` / `.env.example` files for Docker Compose (those set Docker
  Compose project name, not Vultron app config)

### Layer rules preserved

`vultron/config.py` is a neutral module. The import graph stays clean:

```text
vultron/adapters/   → vultron/config.py   ✅  (adapters may import neutral modules)
vultron/core/       → vultron/config.py   ✅  (core may import neutral modules)
vultron/config.py   → vultron/adapters/   ❌  (MUST NOT — neutral modules don't
                                               import from adapters)
vultron/config.py   → vultron/core/       ❌  (MUST NOT — neutral modules don't
                                               import from domain core)
```
