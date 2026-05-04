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

"""Unified application configuration for Vultron.

Provides :class:`AppConfig` (a ``pydantic-settings`` ``BaseSettings`` subclass)
backed by a YAML config file and environment variables.  All Vultron code that
needs runtime settings MUST read them through :func:`get_config` rather than
calling ``os.environ.get()`` directly.

Per specs/configuration.yaml CFG-01 through CFG-06.

Environment variables
---------------------
``VULTRON_CONFIG``
    Path to the YAML configuration file.  Defaults to ``config.yaml`` in the
    working directory.  If set and the file does not exist, startup raises
    :class:`FileNotFoundError`.
``VULTRON_SERVER__BASE_URL``
    Override :attr:`ServerConfig.base_url`.
``VULTRON_SERVER__LOG_LEVEL``
    Override :attr:`ServerConfig.log_level`.
``VULTRON_DATABASE__DB_URL``
    Override :attr:`DatabaseConfig.db_url`.
``VULTRON_MODE``
    Override :attr:`AppConfig.mode` (``prototype`` or ``prod``).
"""

from __future__ import annotations

import logging
import os
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

logger = logging.getLogger(__name__)

#: Valid log-level names accepted by :attr:`ServerConfig.log_level`.
LogLevelName = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class RunMode(StrEnum):
    """Operational mode for the Vultron server.

    ``PROTOTYPE`` activates demo-only endpoints and relaxed validation.
    ``PROD`` enforces production-level constraints.
    """

    PROTOTYPE = "prototype"
    PROD = "prod"


class YamlConfigSource(PydanticBaseSettingsSource):
    """``pydantic-settings`` source that loads configuration from a YAML file.

    The file path is resolved from the ``VULTRON_CONFIG`` environment variable
    (default: ``config.yaml`` in the working directory).  If the variable is
    set but the file does not exist, :class:`FileNotFoundError` is raised at
    startup.  If neither is set and no default file exists, an empty dict is
    returned so all fields fall back to their defaults.
    """

    def _yaml_data(self) -> dict[str, Any]:
        path = os.environ.get("VULTRON_CONFIG", "config.yaml")
        p = Path(path)
        if os.environ.get("VULTRON_CONFIG") and not p.exists():
            raise FileNotFoundError(
                f"VULTRON_CONFIG points to non-existent file: {path}"
            )
        if not p.exists():
            return {}
        logger.debug("Loading configuration from %s", p)
        with p.open() as fh:
            return yaml.safe_load(fh) or {}

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        data = self._yaml_data()
        return data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._yaml_data()


class ServerConfig(BaseModel):
    """HTTP server settings.

    Attributes:
        base_url: Base URL of the Vultron server, used for constructing
            object IDs.  Defaults to ``"http://localhost:7999"``.
        log_level: Root log level name.  Must be one of ``DEBUG``, ``INFO``,
            ``WARNING``, ``ERROR``, or ``CRITICAL``.  Defaults to ``"INFO"``.
    """

    base_url: str = "http://localhost:7999"
    log_level: LogLevelName = "INFO"

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Require an http:// or https:// scheme."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(
                f"base_url must start with http:// or https://, got: {v!r}"
            )
        return v

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: object) -> object:
        """Normalise log level strings to uppercase before validation."""
        if isinstance(v, str):
            return v.upper()
        return v


class DatabaseConfig(BaseModel):
    """Database connection settings.

    Attributes:
        db_url: SQLAlchemy connection URL.  Defaults to
            ``"sqlite:///vultron.db"``.
    """

    db_url: str = "sqlite:///vultron.db"


class AppConfig(BaseSettings):
    """Unified application configuration loaded from YAML and environment.

    Loading precedence (lowest → highest):

    1. YAML config file (path from ``VULTRON_CONFIG``, default
       ``config.yaml``)
    2. Environment variables (``VULTRON_SERVER__BASE_URL``, etc.)

    Attributes:
        server: HTTP server settings.
        database: Database connection settings.
        mode: Operational mode (``prototype`` or ``prod``).
    """

    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    mode: RunMode = RunMode.PROTOTYPE

    model_config = SettingsConfigDict(
        env_prefix="VULTRON_",
        env_nested_delimiter="__",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Precedence: YAML file (lowest) < environment variables (highest).
        # In pydantic-settings 2.x, the FIRST source in the tuple has the
        # HIGHEST priority (it wins in the deep-merge).
        return (env_settings, YamlConfigSource(settings_cls))


_config_cache: AppConfig | None = None


def get_config() -> AppConfig:
    """Return the cached :class:`AppConfig` instance.

    Loads configuration on first call, then returns the same instance for
    all subsequent calls.  Use :func:`reload_config` to force a reload (e.g.
    in tests).

    Returns:
        The active :class:`AppConfig` instance.
    """
    global _config_cache
    if _config_cache is None:
        _config_cache = AppConfig()
    return _config_cache


def reload_config() -> AppConfig:
    """Clear the cached config and return a freshly loaded :class:`AppConfig`.

    Call this in test teardown fixtures (or ``autouse`` fixtures) to ensure
    each test starts with a clean configuration state.

    Returns:
        A newly loaded :class:`AppConfig` instance.
    """
    global _config_cache
    _config_cache = None
    return get_config()
