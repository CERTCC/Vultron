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

    ACTOR0_HOST_PORT=17901 ./integration_tests/demo/run_multi_actor_integration_test.sh
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

# Path to the compose file under test.
from vultron.demo.helpers.cast import (
    ALL_SLOTS,
    CASE_ACTOR,
    CHARACTER_SLOTS,
    COORDINATOR_SLOT,
    REPORTER_SLOT,
    VENDOR_SLOT,
)

_REPO_ROOT = Path(__file__).parents[2]
_COMPOSE_FILE = _REPO_ROOT / "docker" / "docker-compose-multi-actor.yml"

# Expected default host ports per service — they must still appear as
# the *default* value inside the ${VAR:-NNNN} expression.
# Default is 0 (ephemeral) so concurrent test runs don't collide on the host;
# callers that need a fixed port set the env var explicitly (e.g.
# ACTOR0_HOST_PORT=17901).  Derived from the cast so a new cast member cannot
# ship without a configurable host port (DEMOCI-11-020).
_EXPECTED_SERVICE_DEFAULTS: dict[str, int] = {
    slot.name: 0 for slot in ALL_SLOTS
}

# Pattern that matches Docker Compose env-var substitution with a default,
# e.g. "${ACTOR0_HOST_PORT:-0}" as the left side of "HOST:CONTAINER".
_ENV_VAR_PORT_RE = re.compile(r"^\$\{[A-Z0-9_]+:-\d+\}$")


def _load_compose() -> dict[str, Any]:
    """Parse and return the multi-actor compose file as a dict."""
    with _COMPOSE_FILE.open() as fh:
        result: dict[str, Any] = yaml.safe_load(fh)
        return result


class TestMultiActorComposeHostPorts:
    """Host port bindings must be configurable via environment variables."""

    def test_compose_file_exists(self):
        assert _COMPOSE_FILE.exists(), (
            f"Compose file not found: {_COMPOSE_FILE}"
        )

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
                f"env-var substitution (e.g. '${{ACTOR0_HOST_PORT:-7901}}'), "
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

    def test_each_service_publishes_its_own_slots_variable(self):
        """A copy-paste leaving actor3 on ${ACTOR2_HOST_PORT} must fail.

        Derived from the slot name, which is the same half-edited-copy mistake
        ``role_map`` refuses for two roles in one container.
        """
        data = _load_compose()
        for slot in ALL_SLOTS:
            mapping = str(data["services"][slot.name]["ports"][0])
            host_part = mapping.rsplit(":", 1)[0]
            expected = f"{slot.name.upper().replace('-', '_')}_HOST_PORT"
            assert f"${{{expected}:-" in host_part, (
                f"service {slot.name!r} publishes {host_part!r}, not "
                f"${{{expected}:-0}}"
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
                f"with '_HOST_PORT' (e.g. ACTOR0_HOST_PORT)."
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


#: The dedicated CaseActor container every actor container proposes to.
_DEDICATED_CASE_ACTOR_URL = CASE_ACTOR.compose_url

#: Every service that runs a Vultron API server, the case-actor container
#: included (it points at itself).
_API_SERVICES = tuple(slot.name for slot in ALL_SLOTS)


def _env(service: dict[str, Any]) -> dict[str, str]:
    """Return a service's ``environment`` list as a name → value mapping."""
    return dict(
        entry.split("=", 1) for entry in service.get("environment", [])
    )


class TestDedicatedCaseActorTopology:
    """Every container delegates its CaseActor to the dedicated one (#1876).

    CP-08-003 and CP-08-008 require ``VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL``
    to name the dedicated case-actor container, and DEMOMA-06-004 requires the
    demo topology to use it.  A container pointing the URL at itself silently
    restores the co-located shortcut this topology retires.
    """

    def test_every_api_service_names_the_dedicated_case_actor(self):
        services = _load_compose()["services"]
        for name in _API_SERVICES:
            value = _env(services[name]).get(
                "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL"
            )
            assert value == _DEDICATED_CASE_ACTOR_URL, (
                f"Service '{name}' sets VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL"
                f" to {value!r}, not the dedicated case-actor container"
                f" {_DEDICATED_CASE_ACTOR_URL!r} (CP-08-008)."
            )

    def test_case_actor_service_hosts_that_url(self):
        """The URL every container names is the case-actor container's own."""
        env = _env(_load_compose()["services"]["case-actor"])
        assert env["VULTRON_SERVER__BASE_URL"].rstrip("/") == (
            _DEDICATED_CASE_ACTOR_URL
        )
        assert env["VULTRON_ACTOR_ID"] == (
            f"{_DEDICATED_CASE_ACTOR_URL}/actors/case-actor"
        )

    def test_demo_runner_waits_for_the_case_actor(self):
        runner = _load_compose()["services"]["demo-runner"]
        assert runner["depends_on"]["case-actor"] == {
            "condition": "service_healthy"
        }
        assert (
            _env(runner)["VULTRON_CASE_ACTOR_BASE_URL"]
            == _DEDICATED_CASE_ACTOR_URL
        )


class TestDefaultCaseRolesFollowTheCast:
    """Only a fixed-role cast slot declares default case roles.

    A report receiver seats itself with its configured default case roles
    (CP-01-013).  The Coordinator slot needs ``coordinator`` there: without it
    a Coordinator that owns the case holds only ``case_owner``, and the harness
    fails every Coordinator step of its scenario (#5467, DEMOCI-11-013).  A
    character actor must *not* declare one — its role comes from the act that
    seats it (DEMOCI-11-021), and a container default would give it that role
    in every scenario.
    """

    def test_the_vendor_slot_states_the_vendor_role(self):
        env = _env(_load_compose()["services"][VENDOR_SLOT.name])
        assert env.get("VULTRON_ACTOR__DEFAULT_CASE_ROLES") == '["vendor"]'

    def test_the_coordinator_slot_states_the_coordinator_role(self):
        env = _env(_load_compose()["services"][COORDINATOR_SLOT.name])
        assert env.get("VULTRON_ACTOR__DEFAULT_CASE_ROLES") == (
            '["coordinator"]'
        )

    @pytest.mark.parametrize(
        "slot", [REPORTER_SLOT, *CHARACTER_SLOTS], ids=lambda s: s.name
    )
    def test_no_other_slot_states_a_case_role(self, slot):
        """The Reporter slot and every character actor declare none.

        The Reporter's role comes from submitting the report, and this
        container never owns a case.
        """
        env = _env(_load_compose()["services"][slot.name])
        assert "VULTRON_ACTOR__DEFAULT_CASE_ROLES" not in env


_DURATION_RE = re.compile(r"(?:\d+(?:\.\d+)?(?:ms|s|m|h))+")


def _seconds(value: str) -> float:
    """Parse a Compose duration such as ``"2s"`` or ``"1m30s"`` into seconds."""
    assert _DURATION_RE.fullmatch(value), f"unparseable duration {value!r}"
    units = {"ms": 0.001, "s": 1, "m": 60, "h": 3600}
    return sum(
        float(amount) * units[unit]
        for amount, unit in re.findall(r"(\d+(?:\.\d+)?)(ms|s|m|h)", value)
    )


#: The slowest cold start seen in CI: about 31 s importing the app under the
#: reloader, after the ``uv`` build step (#4621).
_SLOWEST_OBSERVED_COLD_START_SECONDS = 31.0

#: Every compose file that starts an actor, with the actor services in it.
_ACTOR_COMPOSE_FILES: dict[str, tuple[str, ...]] = {
    "docker-compose-multi-actor.yml": tuple(slot.name for slot in ALL_SLOTS),
    "docker-compose.yml": ("api-dev",),
}

_ACTOR_HEALTHCHECKS: list[tuple[str, str]] = [
    (compose_file, service)
    for compose_file, services in _ACTOR_COMPOSE_FILES.items()
    for service in services
]


def _healthcheck(compose_file: str, service: str) -> dict[str, Any]:
    with (_REPO_ROOT / "docker" / compose_file).open() as fh:
        svc = yaml.safe_load(fh)["services"][service]
    assert "healthcheck" in svc, (
        f"{compose_file}: {service} has no healthcheck"
    )
    check: dict[str, Any] = svc["healthcheck"]
    return check


@pytest.mark.parametrize(("compose_file", "service"), _ACTOR_HEALTHCHECKS)
class TestActorHealthcheckStartupBudget:
    """An actor that is slow to start must not abort the demo (#4621).

    ``demo-runner`` waits on ``service_healthy`` (DEMOMA-02-002), so a
    healthcheck budget a slow runner outlasts fails the job before the demo
    starts.  Probes inside ``start_period`` do not count toward ``retries``
    and the first success marks the container healthy, so a long start period
    costs a fast runner nothing — provided the probes inside it stay frequent.
    Docker probes every ``start_interval`` (default 5 s) during the start
    period and every ``interval`` after it, so both are pinned.
    """

    def test_start_period_covers_a_slow_cold_start_with_margin(
        self, compose_file: str, service: str
    ):
        check = _healthcheck(compose_file, service)
        start_period = _seconds(check["start_period"])
        assert start_period >= 2 * _SLOWEST_OBSERVED_COLD_START_SECONDS, (
            f"{compose_file}: {service}: start_period {check['start_period']}"
            f" is under twice the slowest observed cold start"
            f" ({_SLOWEST_OBSERVED_COLD_START_SECONDS:.0f} s)"
        )

    @pytest.mark.parametrize("field", ["start_interval", "interval"])
    def test_probes_stay_frequent_so_a_fast_start_is_not_delayed(
        self, compose_file: str, service: str, field: str
    ):
        check = _healthcheck(compose_file, service)
        assert field in check, f"{compose_file}: {service}: no {field}"
        assert _seconds(check[field]) <= 2, (
            f"{compose_file}: {service}: {field} {check[field]} is over 2 s"
        )
