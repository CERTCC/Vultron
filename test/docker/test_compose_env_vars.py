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

"""Tests that docker-compose-multi-actor.yml uses the correct env var names.

The config unification (TASK-CFG) introduced pydantic-settings with
``env_prefix="VULTRON_"`` and ``env_nested_delimiter="__"``, meaning the
correct env var names are:

- ``VULTRON_SERVER__BASE_URL`` for ``ServerConfig.base_url``
- ``VULTRON_DATABASE__DB_URL`` for ``DatabaseConfig.db_url``

The old names ``VULTRON_BASE_URL`` and ``VULTRON_DB_URL`` are silently
ignored by the config system. If docker-compose uses them, each container's
``make_id()`` falls back to the default ``http://localhost:7999``, causing
every actor to be seeded with a ``localhost`` ID — breaking cross-container
routing in the multi-actor integration test.

See GitHub issue #546.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

COMPOSE_FILE = (
    Path(__file__).parent.parent.parent
    / "docker"
    / "docker-compose-multi-actor.yml"
)

ACTOR_SERVICES = ("finder", "vendor", "coordinator", "case-actor", "vendor2")

#: Legacy env var names that must not appear in actor-service environments.
LEGACY_ENV_VARS = ("VULTRON_BASE_URL", "VULTRON_DB_URL")

#: Correct pydantic-settings names that must be present instead.
REQUIRED_ENV_VARS = ("VULTRON_SERVER__BASE_URL", "VULTRON_DATABASE__DB_URL")


@pytest.fixture(scope="module")
def compose_config() -> dict[str, Any]:
    """Load the multi-actor docker-compose YAML once for the module."""
    with COMPOSE_FILE.open() as fh:
        result: dict[str, Any] = yaml.safe_load(fh)
        return result


@pytest.fixture(scope="module")
def actor_service_envs(compose_config: dict) -> dict[str, list[str]]:
    """Return mapping of service name → list of environment strings."""
    services = compose_config.get("services", {})
    result = {}
    for name in ACTOR_SERVICES:
        svc = services.get(name, {})
        result[name] = svc.get("environment", [])
    return result


@pytest.mark.parametrize("service", ACTOR_SERVICES)
@pytest.mark.parametrize("legacy_var", LEGACY_ENV_VARS)
def test_actor_service_does_not_use_legacy_env_var(
    actor_service_envs: dict[str, list[str]],
    service: str,
    legacy_var: str,
) -> None:
    """Actor services must NOT use legacy env var names.

    ``VULTRON_BASE_URL`` and ``VULTRON_DB_URL`` are silently ignored by the
    pydantic-settings config; using them causes actors to be seeded with
    ``localhost`` IDs, breaking cross-container routing (#546).
    """
    env_lines = actor_service_envs[service]
    matching = [
        line for line in env_lines if line.startswith(f"{legacy_var}=")
    ]
    assert not matching, (
        f"Service '{service}' still uses legacy env var '{legacy_var}'. "
        f"Replace with the pydantic-settings name "
        f"('VULTRON_SERVER__BASE_URL' or 'VULTRON_DATABASE__DB_URL')."
    )


@pytest.mark.parametrize("service", ACTOR_SERVICES)
@pytest.mark.parametrize("required_var", REQUIRED_ENV_VARS)
def test_actor_service_has_required_env_var(
    actor_service_envs: dict[str, list[str]],
    service: str,
    required_var: str,
) -> None:
    """Actor services must declare the correct pydantic-settings env vars.

    ``VULTRON_SERVER__BASE_URL`` and ``VULTRON_DATABASE__DB_URL`` are the
    names recognised by ``AppConfig`` (see ``vultron/config.py``).
    """
    env_lines = actor_service_envs[service]
    matching = [
        line for line in env_lines if line.startswith(f"{required_var}=")
    ]
    assert matching, (
        f"Service '{service}' is missing required env var '{required_var}'. "
        f"Ensure docker-compose-multi-actor.yml sets this for every actor "
        f"service so the config system picks it up correctly."
    )
