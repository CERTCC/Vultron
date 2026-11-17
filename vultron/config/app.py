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

"""Application configuration — server, database, and top-level settings.

Per ``specs/configuration.yaml`` CFG-01 through CFG-06, CFG-07-005.

This module is part of the neutral ``vultron/config/`` sub-package. It MUST
NOT import from ``vultron.adapters`` or ``vultron.core``.
"""

from __future__ import annotations

import functools
import logging
import os
import threading
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from vultron.config.actor import ActorConfig
from vultron.config.env_names import ENV_NESTED_DELIMITER, ENV_PREFIX
from vultron.config.ledger import LedgerConfig
from vultron.config.secrets import refuse_secrets_in_file
from vultron.config.shadow import ShadowConfig
from vultron.config.vince import VinceConfig
from vultron.errors import VultronWiringError

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
    returned so all fields fall back to their defaults.  A file that names a
    secret setting, such as ``vince.api_token``, raises
    :class:`~vultron.errors.VultronSecretInConfigFileError`: a secret is read
    only from the environment (VSD-01-004).
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
            data = yaml.safe_load(fh) or {}
        refuse_secrets_in_file(data, self.settings_cls, p)
        return data

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        # pydantic-settings 2.x dispatches via __call__(); this satisfies the ABC.
        data = self._yaml_data()
        return data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._yaml_data()


class ServerConfig(BaseModel):
    """HTTP server settings.

    Attributes:
        base_url: Base URL of the Vultron server, used for constructing
            object IDs.  It starts with ``http://`` or ``https://``.  The value
            includes the API path prefix: an actor's id is the URL that
            reaches it, and a hosted actor is named
            ``{base_url}/actors/{slug}``, so a value without ``/api/v2`` mints
            ids that address nothing (DL-07-006).  The default has the shape
            the compose files set, so a local run resolves actors the way a
            deployed one does.  Defaults to
            ``"http://localhost:7999/api/v2"``.
        log_level: Root log level name.  Must be one of ``DEBUG``, ``INFO``,
            ``WARNING``, ``ERROR``, or ``CRITICAL``.  Defaults to ``"INFO"``.
        ledger_stream_poll_seconds: How often (in seconds) an open demo case
            ledger stream re-reads the actor's DataLayer for new entries
            (``GET /actors/{id}/demo/cases/{case_id}/log/stream``, ADR-0104).
            Must be positive.  Defaults to 0.25.
    """

    base_url: str = "http://localhost:7999/api/v2"
    log_level: LogLevelName = "INFO"
    ledger_stream_poll_seconds: float = Field(default=0.25, gt=0)

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
        actor: Actor policy settings (default CVD roles, case creation policy).
        ledger: Case-ledger timestamp tolerances applied at the CaseActor
            commit boundary (CLP-14-009).
        vince: The VINCE API endpoint and credential the shadow's VINCE
            connector reads cases with; the credential is read only from the
            environment (VSD-01-004).
        shadow: Which case reader the case shadow tool reads cases through,
            and the directory it reads Vultron case-ledger files from.
        mode: Operational mode (``prototype`` or ``prod``).
        pre_bootstrap_queue_timeout_seconds: How long (in seconds) a
            pre-bootstrap inbox queue is held before it expires.  When the
            window lapses, queued activity IDs are dropped and a warning
            is logged (CBT-03-003, CBT-03-005, CBT-03-006).  Override via
            ``VULTRON_PRE_BOOTSTRAP_QUEUE_TIMEOUT_SECONDS``.  Defaults to
            300 (5 minutes).
        max_inbox_retry_attempts: Maximum cumulative processing attempts for
            a single inbox activity before it is moved to the dead-letter
            store (IE-06-004).  Matches the outbox default of 12 so that
            inbox and outbox share the same retry budget.  Override via
            ``VULTRON_MAX_INBOX_RETRY_ATTEMPTS``.  Defaults to 12.
        max_object_fetch_attempts: Maximum attempts to fetch one object a
            received activity names before the fetch fails and the waiting
            activity goes on without it (AKM-05-008).  Attempts back off
            exponentially; a 4xx answer ends the fetch at once.  Override via
            ``VULTRON_MAX_OBJECT_FETCH_ATTEMPTS``.  Defaults to 3.
        object_fetch_timeout_seconds: Timeout of each fetch attempt, in
            seconds (AKM-05-008).  It matches the delivery timeout
            (SYNC-05-004).  Override via
            ``VULTRON_OBJECT_FETCH_TIMEOUT_SECONDS``.  Defaults to 30.
        verification_key_fetch_timeout_seconds: Timeout of the one attempt to
            fetch the profile that lists a proof's key, in seconds.  The
            fetch runs before the sender is verified, so it is made once,
            with no retry, and its wait is kept short (SIG-02-001).
            Override via ``VULTRON_VERIFICATION_KEY_FETCH_TIMEOUT_SECONDS``.
            Defaults to 5.
    """

    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    actor: ActorConfig = ActorConfig()
    ledger: LedgerConfig = LedgerConfig()
    vince: VinceConfig = VinceConfig()
    shadow: ShadowConfig = ShadowConfig()
    mode: RunMode = RunMode.PROTOTYPE
    pre_bootstrap_queue_timeout_seconds: int = 300
    max_inbox_retry_attempts: int = 12
    max_object_fetch_attempts: int = Field(default=3, ge=1)
    object_fetch_timeout_seconds: float = Field(default=30.0, gt=0)
    verification_key_fetch_timeout_seconds: float = Field(default=5.0, gt=0)

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_nested_delimiter=ENV_NESTED_DELIMITER,
        # A validation error names the setting, and pydantic does not append
        # the input it was given: the input can be a secret, such as a VINCE
        # credential written as the whole ``vince:`` section (VSD-01-005).
        # A section model's own setting is overruled by this outermost one.
        # A field validator's own message may still quote a non-secret value.
        hide_input_in_errors=True,
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
        # HIGHEST priority (it wins in the deep-merge).  No ``.env`` file and
        # no secrets directory is read, on purpose: a secret comes from the
        # process environment only (VSD-01-004, SHD-02-003).
        return (env_settings, YamlConfigSource(settings_cls))


class _ProcessWide(Enum):
    """Marks a scope whose app holds no config of its own (ADR-0206)."""

    CONFIG = "process-wide"


_PROCESS_WIDE = _ProcessWide.CONFIG

# The config of the app whose work is running in this context, or
# ``_PROCESS_WIDE`` for an app that holds none.  ``None`` means no app scope
# is entered at all.  A context variable, so concurrent requests to two apps
# in one process each see their own, and an ``asyncio`` task or a
# ``contextvars.copy_context()`` run inherits the scope it was started in.
_APP_CONFIG_SCOPE: ContextVar[AppConfig | _ProcessWide | None] = ContextVar(
    "vultron_app_config_scope", default=None
)


# The running apps that hold their own config in this process.  While any
# is, the process-wide config is no node's config, so a read made in no app
# scope is a path that lost its app's config and raises (ADR-0206).
class _HeldAppConfigs:
    """A thread-safe record of the running apps that hold their own config.

    Each hold is a token rather than a count, so releasing one is idempotent:
    a hold released twice (a test's leak guard drops it, then its lifespan
    exits) cannot leave the record short and the refusal stuck on.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._holds: set[object] = set()

    def __bool__(self) -> bool:
        return bool(self._holds)

    def snapshot(self) -> frozenset[object]:
        """Return the holds running now."""
        with self._lock:
            return frozenset(self._holds)

    def hold(self) -> object:
        """Record a new hold and return its token."""
        token = object()
        with self._lock:
            self._holds.add(token)
        return token

    def release(self, token: object) -> None:
        """Drop the hold *token*; a token already dropped is ignored."""
        with self._lock:
            self._holds.discard(token)


_HELD_APP_CONFIGS = _HeldAppConfigs()


@functools.cache
def _process_config() -> AppConfig:
    return AppConfig()


def get_config() -> AppConfig:
    """Return the :class:`AppConfig` of the app this code runs for.

    Inside :func:`app_config_scope` for an app that holds its own config,
    that config is returned (ADR-0206).  Otherwise the process-wide config is
    returned: loaded on first call, then the same instance for all later
    calls.  That cache is owned by ``functools.cache`` rather than a module
    global; use :func:`clear_config_cache` to drop it (the next call reloads)
    or :func:`reload_config` to drop it and reload at once.

    Returns:
        The active :class:`AppConfig` instance.

    Raises:
        VultronWiringError: the call is in no app scope while an app holding
            its own config runs in this process (:func:`holding_app_config`).
            The caller lost its app's scope, and the process-wide config is
            not its node's config, so it is never returned in its place.
    """
    scoped = _APP_CONFIG_SCOPE.get()
    if isinstance(scoped, AppConfig):
        return scoped
    if scoped is None and _HELD_APP_CONFIGS:
        raise VultronWiringError(
            "get_config() was called in no app scope while an app holding "
            "its own AppConfig runs in this process, so the process-wide "
            "config is not this caller's node config. Run the work inside "
            "its app's app_config_scope() (copy the context into a thread "
            "or task it starts) (ADR-0206)."
        )
    return _process_config()


@contextmanager
def app_config_scope(config: AppConfig | None) -> Generator[None]:
    """Run the body as work of an app whose config is *config*.

    Inside the body, :func:`get_config` and :func:`load_actor_config` return
    *config*.  With ``None`` the body is work of an app that holds no config
    of its own, and they return the process-wide config.  Scopes nest; the
    previous scope is restored on exit, even when the body raises.

    Args:
        config: The app's own config, or ``None`` for an app that has none.
    """
    token = _APP_CONFIG_SCOPE.set(
        config if config is not None else _PROCESS_WIDE
    )
    try:
        yield
    finally:
        _APP_CONFIG_SCOPE.reset(token)


@contextmanager
def holding_app_config(config: AppConfig) -> Generator[None]:
    """Run an app that holds its own *config* for the body's duration.

    Enters :func:`app_config_scope` for *config* and, until exit, counts the
    app as running.  While any such app runs, :func:`get_config` in no app
    scope raises :class:`~vultron.errors.VultronWiringError` instead of
    returning the process-wide config (ADR-0206).  An app's lifespan wraps
    itself in this.

    Args:
        config: The app's own config.
    """
    hold = _HELD_APP_CONFIGS.hold()
    try:
        with app_config_scope(config):
            yield
    finally:
        _HELD_APP_CONFIGS.release(hold)


def clear_config_cache() -> None:
    """Drop the cached :class:`AppConfig` without loading a new one.

    The next :func:`get_config` call reloads from the environment as it stands
    then.  This is the test-teardown form (CFG-06-003): unlike
    :func:`reload_config`, it does not read the environment while a test's
    ``monkeypatch`` changes are still in force.  An app's own config is not
    cached here and is not dropped.
    """
    _process_config.cache_clear()


def load_actor_config() -> ActorConfig:
    """Return the local actor's policy :class:`~vultron.config.actor.ActorConfig`.

    Delegates to :func:`get_config` so actor policy is read from the same
    unified config as all other application settings (CFG-07-005), and from
    the app's own config inside its :func:`app_config_scope` (ADR-0206).

    Configuration sources, in decreasing priority:

    1. ``VULTRON_ACTOR__AUTO_CREATE_CASE`` / ``VULTRON_ACTOR__DEFAULT_CASE_ROLES``
       environment variables.
    2. ``actor:`` section in the YAML file at ``VULTRON_CONFIG``
       (default: ``config.yaml``).
    3. Hard-coded defaults (``auto_create_case=True``,
       ``default_case_roles=[]``).

    Returns:
        The :class:`~vultron.config.actor.ActorConfig` from the active
        :class:`AppConfig`.
    """
    return get_config().actor


def reload_config() -> AppConfig:
    """Clear the cached config and return a freshly loaded :class:`AppConfig`.

    This is the process-wide config, whatever app scope the caller is in; an
    app's own config is not reloaded.  Call this in test teardown fixtures
    (or ``autouse`` fixtures) to ensure each test starts with a clean
    configuration state.

    Returns:
        A newly loaded :class:`AppConfig` instance.
    """
    clear_config_cache()
    return _process_config()


@contextmanager
def config_override(**env_updates: str) -> Generator[AppConfig]:
    """Atomically patch env vars, reload the config cache, and restore on exit.

    Sets each key in *env_updates* as an environment variable, reloads the
    config cache, yields the updated :class:`AppConfig`, then restores the
    original environment values and reloads again in a ``finally`` block so
    that the restore always happens even when the body raises (CFG-06-006).

    It acts on the process-wide config only: the yielded config is the
    process-wide one, and an app holding its own config (ADR-0206) keeps
    reading that config inside its scope, unaffected by the override.

    This makes the incorrect ``monkeypatch.undo()``-after-``reload_config()``
    ordering impossible by construction (CONCERN-2323).

    Example::

        with config_override(VULTRON_SERVER__BASE_URL="http://test:8080") as cfg:
            assert cfg.server.base_url == "http://test:8080"
        # env and cache are restored here

    Args:
        **env_updates: Environment variable names mapped to override values.

    Yields:
        The updated :class:`AppConfig` instance after reloading.
    """
    originals: dict[str, str | None] = {
        key: os.environ.get(key) for key in env_updates
    }
    for key, value in env_updates.items():
        os.environ[key] = value
    try:
        yield reload_config()
    finally:
        for key, original in originals.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original
        reload_config()
