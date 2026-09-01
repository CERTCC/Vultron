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
related_notes:
  - notes/testing-pitfalls.md
---

# Configuration Management — Implementation Notes

## Background

IDEA-260402-01 (design session 2026-04-23) established that Vultron config
files MUST use YAML for readability and MUST be loaded into Pydantic-backed
structured objects for type safety. This note captures the design decisions
and implementation guidance for the `vultron/config/` sub-package and the
aligned `SeedConfig` refactor. The `vultron/config.py` flat module shown in
the historical sections below was replaced by the sub-package in issue #1342;
see § "Current Architecture" for the live layout.

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

## Implementation Pattern

### AppConfig with pydantic-settings

```python
# vultron/config/app.py
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

actor:
  auto_create_case: true
  default_case_roles: []
  case_actor_service_url: "http://case-actor:7999/api/v2"
```

The `actor:` section maps to `AppConfig.actor` (`ActorConfig`). It controls
actor-policy defaults used by BT nodes and the production adapter:

- `auto_create_case`: when `true` (default), create a `VulnerabilityCase`
  immediately on `Offer(Report)` receipt (ADR-0015 Option 4).  Set to
  `false` to defer case creation so a pre-case ACK can be sent first
  (CM-15-001, issue #1133).
- `default_case_roles`: list of CVD role strings (e.g. `["coordinator"]`)
  assigned to the local actor when it creates or takes ownership of a case.
  `CVDRole.CASE_OWNER` is always appended at participant-creation time
  (BTND-05-002) and does not need to be listed here.
- `case_actor_service_url`: base URL of the dedicated CaseActor container
  (e.g., `http://case-actor:7999/api/v2`). Required for any actor whose BT
  may run the `engage-case` path (i.e., case-creating actors). Absence causes
  `ResolveCaseActorUrlsNode` to return `FAILURE` with a clear error message.
  `None` by default; MUST be supplied via `VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL`
  or the `config.yaml` `actor:` block. See CP-08-001, `notes/case-proposal.md`.

---

## Environment Variable Reference

| Env var | Maps to | Default |
|---------|---------|---------|
| `VULTRON_CONFIG` | path to config.yaml | `config.yaml` |
| `VULTRON_SERVER__BASE_URL` | `server.base_url` | `http://localhost:7999` |
| `VULTRON_SERVER__LOG_LEVEL` | `server.log_level` | `INFO` |
| `VULTRON_DATABASE__DB_URL` | `database.db_url` | `sqlite:///vultron.db` |
| `VULTRON_ACTOR__AUTO_CREATE_CASE` | `actor.auto_create_case` | `true` |
| `VULTRON_ACTOR__DEFAULT_CASE_ROLES` | `actor.default_case_roles` | `[]` |
| `VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL` | `actor.case_actor_service_url` | `None` |

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

### Preferred: `config_override()` context manager (CFG-06-006)

Use `config_override()` when a test needs to override `AppConfig` values.  It
atomically patches `os.environ`, reloads the cache, and restores both on exit —
even when the body raises.  This makes the incorrect reload-before-undo ordering
impossible by construction (CONCERN-2323):

```python
from vultron.config import config_override

def test_env_override():
    with config_override(VULTRON_SERVER__BASE_URL="http://myserver:8080") as cfg:
        assert cfg.server.base_url == "http://myserver:8080"
    # env and cache are restored here, regardless of exception
```

For tests that only need to reset the cache (no env override), null
`_config_cache` directly in teardown rather than calling `reload_config()`:

```python
import vultron.config.app as _cfg_module

@pytest.fixture(autouse=True)
def reset_config():
    yield
    # Null the cache directly — calling reload_config() would re-read the env
    # while monkeypatch patches are still active, baking stale values in.
    _cfg_module._config_cache = None
```

### The `reload_config()` ordering footgun

`_config_cache` is a module-level singleton.  `reload_config()` clears it and
immediately calls `get_config()`, which re-reads `os.environ` at that instant.
`pytest`'s `monkeypatch` undoes env changes in fixture **teardown**, *after* the
teardown body runs.

```text
BAD teardown order:
    reload_config()      ← re-reads env while patches are still active
    monkeypatch.undo()   ← too late: stale value is already cached

CORRECT teardown order:
    monkeypatch.undo()   ← patches gone before reload
    reload_config()      ← re-reads clean env

BEST: use config_override() — ordering is correct by construction
```

A leaked stale value causes every subsequent test that reads `get_config()` to
see the wrong host.  In the demo suite this surfaces as "no routable recipients"
failures whose order dependency looks random under `pytest-randomly` (ISSUE-2086).

The session-scoped `restore_case_actor_url_after_each_test` autouse fixture in
`test/demo/conftest.py` detects and repairs function-scoped leaks, but
module/class/session-scoped fixtures must still use correct ordering themselves.

### `_TestClientRouter` WARNING for unexpected drops

`_TestClientRouter.emit` (in `test/demo/conftest.py`) drops deliveries when no
client is registered for the recipient's base URL.  This is intentional for
known-fictional external URLs such as `vultron.example` — those MUST NOT become
real HTTP requests.

However, the same silence swallows *unintentional* misrouting.  A stale-config
leak that causes `Create(CaseProposal)` to be addressed to an unregistered
`.test` host vanishes without any WARNING.  The failure surfaces several steps
downstream ("no routable recipients") with no pointer to the real cause.

The fix: maintain a `_KNOWN_FICTIONAL_HOSTS` allowlist in `test/demo/conftest.py`
(e.g. `{"vultron.example"}`).  Drops matching the allowlist keep `DEBUG` logging;
drops outside it upgrade to `WARNING` — a `.test` host that was not registered
is almost always a config bug.

### Legacy pattern (raw monkeypatch + explicit test_config.py)

```python
# test/test_config.py
import pytest
import vultron.config.app as _cfg_module  # _config_cache lives in app.py, not __init__
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

## Current Architecture: `vultron/config/` Sub-Package

`vultron/config.py` was converted to a `vultron/config/` sub-package in
issue #1342 (CFG-07-005, CFG-07-006). The current layout:

```text
vultron/
  enums/
    __init__.py  ← re-exports CVDRole, serialize_roles, validate_roles
    roles.py     ← CVDRole, serialize_roles, validate_roles
                   (moved from vultron/core/states/roles.py)
  config/
    __init__.py  ← public re-exports: AppConfig, ActorConfig, get_config,
                   reload_config, RunMode, ServerConfig, DatabaseConfig,
                   YamlConfigSource
    app.py       ← AppConfig, ServerConfig, DatabaseConfig, RunMode,
                   YamlConfigSource, get_config(), reload_config()
    actor.py     ← ActorConfig (moved from vultron/core/models/actor_config.py)
```

The sub-package is a **neutral module**: it MUST NOT import from
`vultron/adapters/`, `vultron/wire/`, or FastAPI. It sits alongside
`vultron/errors.py` as a shared-access layer. `actor.py` imports `CVDRole` from
`vultron.enums.roles` — not from `vultron/core/` — satisfying that constraint.

`AppConfig` has an `actor: ActorConfig` field (default: `ActorConfig()`) so
production code reads actor policy via `get_config().actor`.  Actor config is
also available from the YAML `actor:` section or `VULTRON_ACTOR__*` env vars.

---

## Key-Presence Check Required Before `model_validate`

(ISSUE-1343, 2026-07-15; see `specs/configuration.yaml` CFG-07-008)

Any YAML sub-block loader MUST check whether the target key is present in the
raw dict **before** calling `model_validate`:

```python
# ❌ WRONG — model_validate({}) succeeds silently on an all-defaults model
raw = yaml.safe_load(fh) or {}
return ActorConfig.model_validate(raw.get("local_actor", {}))

# ✅ CORRECT — return None when key is absent so caller falls through
raw = yaml.safe_load(fh) or {}
if "local_actor" not in raw:
    return None
return ActorConfig.model_validate(raw["local_actor"])
```

**Why `model_validate({})` is wrong**: Pydantic's `model_validate` on a
model where every field has a default does not distinguish "field absent from
source" from "field explicitly set to default". A dict with no keys validates
successfully and returns an all-defaults instance. If the loader returns that
instance, `load_actor_config()` exits early — silently ignoring
`VULTRON_ACTOR__*` env vars and violating the YAML → env → defaults
resolution order.

**Pattern**: Whenever a loader reads a YAML sub-block and is supposed to fall
back to a secondary source, check for key *presence* (not just type), then
validate. This applies to all config loaders that have a "key absent means
skip this source" contract.

---

## SeedConfig Refactoring

`SeedConfig` in `vultron/demo/seed_config.py` MUST be migrated to
`pydantic-settings` `BaseSettings` (issue #1334). Key changes:

- Subclass `BaseSettings` instead of `BaseModel`
- Drop `from_env()` and `from_file()` classmethods — `BaseSettings` handles
  source merging automatically
- Keep `load()` only if `VULTRON_SEED_CONFIG` path override cannot be
  expressed as a `YamlConfigSource`; otherwise remove it
- `LocalActorConfig` MUST become a plain `BaseModel` carrying only bootstrap
  identity fields (`name`, `actor_type`, `id_`) — it MUST NOT extend
  `ActorConfig` (CFG-07-007). Actor policy fields (`auto_create_case`,
  `default_case_roles`) are now owned by `AppConfig.actor`
- `PeerActorConfig` stays as a plain `BaseModel` sub-model

---

## Relation to Existing Code

### Layer rules

`vultron/config/` is a neutral sub-package. The import graph:

```text
vultron/adapters/   → vultron/config/   ✅  (adapters may import neutral modules)
vultron/core/       → vultron/config/   ✅  (core may import neutral modules)
vultron/config/     → vultron/adapters/ ❌  (MUST NOT)
vultron/config/     → vultron/core/     ❌  (MUST NOT — use vultron/enums/ instead)
vultron/enums/      → vultron/core/     ❌  (MUST NOT — enums are bottom-of-stack)
vultron/enums/      → vultron/config/   ❌  (MUST NOT)
```

### Docker seed-config YAML files

Files in `docker/seed-configs/` use the `local_actor:` block for bootstrap
identity (`name`, `actor_type`, `id`). Actor policy fields that were previously
in `local_actor:` (`auto_create_case`, `default_case_roles`) must move to a
separate `config.yaml` `actor:` section in those deployments.

## A Test That Needs `VULTRON_*` Config MUST Set It Itself

The flip side of the teardown-ordering rule above: fixing a leak removes config
that downstream tests may have been silently borrowing. `test_create_tree.py` and
`nodes/test_communication.py` both run `ResolveCaseActorUrlsNode` (via
`CreateCaseActorNode` / `CreateCaseBT`), which returns FAILURE when
`case_actor_service_url` is None (CP-08-002/003) — yet neither module set it.
They passed only because another module leaked the value into the process-global
cache first, and failed in isolation or in a subset run (#1897).

Each module that depends on a `VULTRON_*` setting needs its own autouse fixture
setting it, using the `monkeypatch.undo()`-then-`reload_config()` teardown order.
Verify with a targeted run, not just the full suite — a module that only passes in
a full-suite run is order-dependent, not passing.

Source: #1897 / PR #2126
