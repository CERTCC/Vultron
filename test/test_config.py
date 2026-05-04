#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Tests for vultron/config.py — unified configuration system.

Per specs/configuration.yaml CFG-06-001 through CFG-06-005.
"""

import pytest

from vultron.config import (
    RunMode,
    ServerConfig,
    get_config,
    reload_config,
)


@pytest.fixture(autouse=True)
def reset_config(monkeypatch, tmp_path):
    """Ensure each test starts with a clean config cache (CFG-06-003).

    Changes the working directory to a temporary path so that no real
    ``config.yaml`` is inadvertently picked up.  Clears all ``VULTRON_``
    config env vars so that defaults are isolated, then restores state via
    monkeypatch teardown.  Clears the config cache in teardown.
    """
    monkeypatch.chdir(tmp_path)
    # Clear all Vultron config env vars so tests see true defaults
    for var in (
        "VULTRON_CONFIG",
        "VULTRON_SERVER__BASE_URL",
        "VULTRON_SERVER__LOG_LEVEL",
        "VULTRON_DATABASE__DB_URL",
        "VULTRON_MODE",
    ):
        monkeypatch.delenv(var, raising=False)
    reload_config()
    yield
    # Clear cache after teardown; guard against FileNotFoundError when
    # VULTRON_CONFIG still points to a missing file set by the test body
    # (monkeypatch reverts env vars only after this fixture's teardown).
    import vultron.config as _cfg_module

    _cfg_module._config_cache = None


# ---------------------------------------------------------------------------
# CFG-06-005: application starts with all defaults (no file, no env vars)
# ---------------------------------------------------------------------------


def test_defaults_server_base_url():
    cfg = get_config()
    assert cfg.server.base_url == "http://localhost:7999"


def test_defaults_server_log_level():
    cfg = get_config()
    assert cfg.server.log_level == "INFO"


def test_defaults_database_db_url():
    cfg = get_config()
    assert cfg.database.db_url == "sqlite:///vultron.db"


def test_defaults_mode():
    cfg = get_config()
    assert cfg.mode == RunMode.PROTOTYPE


# ---------------------------------------------------------------------------
# CFG-01-002: get_config() returns a cached instance
# ---------------------------------------------------------------------------


def test_get_config_returns_same_instance():
    cfg1 = get_config()
    cfg2 = get_config()
    assert cfg1 is cfg2


# ---------------------------------------------------------------------------
# CFG-01-003: reload_config() clears the cache
# ---------------------------------------------------------------------------


def test_reload_config_returns_new_instance():
    cfg1 = get_config()
    cfg2 = reload_config()
    assert cfg1 is not cfg2


# ---------------------------------------------------------------------------
# CFG-06-001 / CFG-06-004: env vars override defaults
# ---------------------------------------------------------------------------


def test_env_override_base_url(monkeypatch):
    monkeypatch.setenv("VULTRON_SERVER__BASE_URL", "http://myserver:8080")
    reload_config()
    assert get_config().server.base_url == "http://myserver:8080"


def test_env_override_log_level(monkeypatch):
    monkeypatch.setenv("VULTRON_SERVER__LOG_LEVEL", "DEBUG")
    reload_config()
    assert get_config().server.log_level == "DEBUG"


def test_env_override_db_url(monkeypatch):
    monkeypatch.setenv("VULTRON_DATABASE__DB_URL", "sqlite:///:memory:")
    reload_config()
    assert get_config().database.db_url == "sqlite:///:memory:"


def test_env_override_mode(monkeypatch):
    monkeypatch.setenv("VULTRON_MODE", "prod")
    reload_config()
    assert get_config().mode == RunMode.PROD


# ---------------------------------------------------------------------------
# CFG-06-002: YAML config file loading
# ---------------------------------------------------------------------------


def test_yaml_file_sets_log_level(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("server:\n  log_level: DEBUG\n")
    monkeypatch.setenv("VULTRON_CONFIG", str(cfg_file))
    reload_config()
    assert get_config().server.log_level == "DEBUG"


def test_yaml_file_sets_base_url(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("server:\n  base_url: http://yaml-host:9000\n")
    monkeypatch.setenv("VULTRON_CONFIG", str(cfg_file))
    reload_config()
    assert get_config().server.base_url == "http://yaml-host:9000"


def test_yaml_file_sets_db_url(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("database:\n  db_url: sqlite:///yaml.db\n")
    monkeypatch.setenv("VULTRON_CONFIG", str(cfg_file))
    reload_config()
    assert get_config().database.db_url == "sqlite:///yaml.db"


# ---------------------------------------------------------------------------
# CFG-06-004: env vars override YAML values for the same field
# ---------------------------------------------------------------------------


def test_env_overrides_yaml_log_level(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("server:\n  log_level: DEBUG\n")
    monkeypatch.setenv("VULTRON_CONFIG", str(cfg_file))
    monkeypatch.setenv("VULTRON_SERVER__LOG_LEVEL", "ERROR")
    reload_config()
    assert get_config().server.log_level == "ERROR"


def test_env_overrides_yaml_base_url(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("server:\n  base_url: http://yaml-host:9000\n")
    monkeypatch.setenv("VULTRON_CONFIG", str(cfg_file))
    monkeypatch.setenv("VULTRON_SERVER__BASE_URL", "http://env-host:1234")
    reload_config()
    assert get_config().server.base_url == "http://env-host:1234"


# ---------------------------------------------------------------------------
# CFG-02-006: non-existent file when VULTRON_CONFIG is set raises an error
# ---------------------------------------------------------------------------


def test_missing_config_file_raises_when_vultron_config_set(monkeypatch):
    monkeypatch.setenv("VULTRON_CONFIG", "/nonexistent/path/config.yaml")
    with pytest.raises(FileNotFoundError, match="VULTRON_CONFIG"):
        reload_config()


# ---------------------------------------------------------------------------
# CFG-02-007: no config file and VULTRON_CONFIG unset → start with defaults
# ---------------------------------------------------------------------------


def test_no_config_file_no_env_uses_defaults():
    # tmp_path + no VULTRON_CONFIG → defaults only
    cfg = get_config()
    assert cfg.server.base_url == "http://localhost:7999"
    assert cfg.database.db_url == "sqlite:///vultron.db"


# ---------------------------------------------------------------------------
# ServerConfig field validation
# ---------------------------------------------------------------------------


def test_server_config_rejects_invalid_base_url():
    with pytest.raises(Exception):
        ServerConfig(base_url="not-a-url")


def test_server_config_normalises_log_level_to_uppercase():
    cfg = ServerConfig(log_level="debug")  # type: ignore[arg-type]
    assert cfg.log_level == "DEBUG"


def test_server_config_rejects_invalid_log_level():
    with pytest.raises(Exception):
        ServerConfig(log_level="VERBOSE")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RunMode
# ---------------------------------------------------------------------------


def test_run_mode_prototype_value():
    assert RunMode.PROTOTYPE == "prototype"


def test_run_mode_prod_value():
    assert RunMode.PROD == "prod"
