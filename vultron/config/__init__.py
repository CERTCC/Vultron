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

Per ``specs/configuration.yaml`` CFG-01 through CFG-07.

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
``VULTRON_LEDGER__CLOCK_SKEW_TOLERANCE_SECONDS``
    Override :attr:`LedgerConfig.clock_skew_tolerance_seconds` (CLP-14-009).
``VULTRON_LEDGER__FUTURE_TOLERANCE_SECONDS``
    Override :attr:`LedgerConfig.future_tolerance_seconds` (CLP-14-009).
``VULTRON_LEDGER__STALENESS_WINDOW_DAYS``
    Override :attr:`LedgerConfig.staleness_window_days` (CLP-14-009).
"""

from vultron.config.actor import ActorConfig
from vultron.config.ledger import LedgerConfig
from vultron.config.app import (
    AppConfig,
    DatabaseConfig,
    RunMode,
    ServerConfig,
    YamlConfigSource,
    config_override,
    get_config,
    load_actor_config,
    reload_config,
)

__all__ = [
    "ActorConfig",
    "AppConfig",
    "DatabaseConfig",
    "LedgerConfig",
    "RunMode",
    "ServerConfig",
    "YamlConfigSource",
    "config_override",
    "get_config",
    "load_actor_config",
    "reload_config",
]
