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

"""Tests for docker-compose-multi-actor.yml configuration (BUG-2026040104).

Verifies that host-side port bindings in docker-compose-multi-actor.yml are
configurable via environment variables so that parallel runs or a concurrent
development stack cannot cause "port is already allocated" failures.

Each actor service must publish its host port as an env-var interpolation
(``${VAR:-default}`` syntax) rather than a hardcoded number.  Docker Compose
resolves these at startup time, which allows callers to override them:

    FINDER_HOST_PORT=17901 ./integration_tests/demo/run_multi_actor_integration_test.sh
"""

import re
from pathlib import Path
from typing import Any

import yaml

# Path to the compose file under test.
_REPO_ROOT = Path(__file__).parents[2]
_COMPOSE_FILE = _REPO_ROOT / "docker" / "docker-compose-multi-actor.yml"

# Expected default host ports per service — they must still appear as
# the *default* value inside the ${VAR:-NNNN} expression.
_EXPECTED_SERVICE_DEFAULTS: dict[str, int] = {
    "finder": 7901,
    "vendor": 7902,
    "case-actor": 7903,
    "coordinator": 7904,
    "vendor2": 7905,
}

# Pattern that matches Docker Compose env-var substitution with a default,
# e.g. "${FINDER_HOST_PORT:-7901}" as the left side of "HOST:CONTAINER".
_ENV_VAR_PORT_RE = re.compile(r"^\$\{[A-Z0-9_]+:-\d+\}$")


def _load_compose() -> dict[str, Any]:
    """Parse and return the multi-actor compose file as a dict."""
    with _COMPOSE_FILE.open() as fh:
        result: dict[str, Any] = yaml.safe_load(fh)
        return result


class TestMultiActorComposeHostPorts:
    """Host port bindings must be configurable via environment variables."""

    def test_compose_file_exists(self):
        assert (
            _COMPOSE_FILE.exists()
        ), f"Compose file not found: {_COMPOSE_FILE}"

    def test_all_actor_services_have_port_mappings(self):
        """Every actor service must expose exactly one port mapping."""
        data = _load_compose()
        for service_name in _EXPECTED_SERVICE_DEFAULTS:
            svc = data["services"][service_name]
            ports = svc.get("ports", [])
            assert len(ports) == 1, (
                f"Service '{service_name}' must have exactly one port mapping, "
                f"got {ports!r}"
            )

    def test_host_ports_use_env_var_substitution(self):
        """Host port side of each mapping must use ${VAR:-default} syntax.

        This is the regression test for BUG-2026040104: hardcoded host ports
        make parallel or concurrent runs impossible because both stacks try
        to bind the same host port, causing Docker to fail with
        'port is already allocated'.
        """
        data = _load_compose()
        for service_name in _EXPECTED_SERVICE_DEFAULTS:
            svc = data["services"][service_name]
            ports = svc.get("ports", [])
            assert ports, f"Service '{service_name}' has no port mappings"
            mapping = str(ports[0])
            host_part, _container = mapping.rsplit(":", 1)
            assert _ENV_VAR_PORT_RE.match(host_part), (
                f"Service '{service_name}' host port {host_part!r} must use "
                f"env-var substitution (e.g. '${{FINDER_HOST_PORT:-7901}}'), "
                f"not a hardcoded value.  Hardcoded ports prevent concurrent "
                f"runs and cause 'port is already allocated' errors."
            )

    def test_host_port_defaults_match_expected_values(self):
        """Default port values inside the env-var expressions must be correct."""
        data = _load_compose()
        for service_name, expected_port in _EXPECTED_SERVICE_DEFAULTS.items():
            svc = data["services"][service_name]
            ports = svc.get("ports", [])
            assert ports, f"Service '{service_name}' has no port mappings"
            mapping = str(ports[0])
            host_part, _container = mapping.rsplit(":", 1)
            # Extract the default from ${VAR:-NNNN}
            m = re.search(r":-(\d+)\}", host_part)
            assert m is not None, (
                f"Service '{service_name}' host port {host_part!r} does not "
                f"contain a default value in ${{VAR:-default}} syntax."
            )
            actual_default = int(m.group(1))
            assert actual_default == expected_port, (
                f"Service '{service_name}' default host port should be "
                f"{expected_port}, got {actual_default}."
            )

    def test_env_var_names_follow_convention(self):
        """Env var names must follow UPPER_SNAKE_CASE and end with _HOST_PORT."""
        data = _load_compose()
        for service_name in _EXPECTED_SERVICE_DEFAULTS:
            svc = data["services"][service_name]
            ports = svc.get("ports", [])
            assert ports, f"Service '{service_name}' has no port mappings"
            mapping = str(ports[0])
            host_part, _container = mapping.rsplit(":", 1)
            m = re.search(r"\$\{([A-Z0-9_]+):-", host_part)
            assert m is not None, (
                f"Service '{service_name}': could not extract env var name "
                f"from {host_part!r}."
            )
            var_name = m.group(1)
            assert var_name.endswith("_HOST_PORT"), (
                f"Service '{service_name}' env var {var_name!r} should end "
                f"with '_HOST_PORT' (e.g. FINDER_HOST_PORT)."
            )

    def test_container_port_is_always_7999(self):
        """The container-side port must remain 7999 for every actor service."""
        data = _load_compose()
        for service_name in _EXPECTED_SERVICE_DEFAULTS:
            svc = data["services"][service_name]
            ports = svc.get("ports", [])
            assert ports, f"Service '{service_name}' has no port mappings"
            mapping = str(ports[0])
            _host_part, container_part = mapping.rsplit(":", 1)
            assert container_part == "7999", (
                f"Service '{service_name}' container port must be 7999, "
                f"got {container_part!r}."
            )
