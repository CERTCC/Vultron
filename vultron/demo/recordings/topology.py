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

"""The Docker demo's container layout, read from its compose file."""

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml

from vultron.demo.helpers.actor_roles import ActorRole
from vultron.enums.roles import CVDRole
from vultron.errors import DemoRecordingError

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_PATH = REPO_ROOT / "docker" / "docker-compose-multi-actor.yml"

#: The compose service whose environment maps container slots to URLs.
_RUNNER_SERVICE = "demo-runner"
_CASE_ROLES_ENV = "VULTRON_ACTOR__DEFAULT_CASE_ROLES"
_CASE_ACTOR_SERVICE_ENV = "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL"


@dataclass(frozen=True)
class ContainerTopology:
    """The Docker demo's container layout, as the recorder needs it.

    Attributes:
        slot_urls: Base URL of each cast container, keyed by the slot's env
            var (``VULTRON_ACTOR1_BASE_URL`` → ``http://actor1:7999/api/v2``).
        case_roles: Each container's ``VULTRON_ACTOR__DEFAULT_CASE_ROLES``,
            keyed by host name.  A container without the setting is absent.
        case_actor_service_url: The CaseActor every container proposes to.
    """

    slot_urls: dict[str, str]
    case_roles: dict[str, list[CVDRole]]
    case_actor_service_url: str

    def url_for(self, role: ActorRole) -> str:
        """Return the base URL of the container slot *role* runs in."""
        try:
            return self.slot_urls[role.url_env]
        except KeyError:
            raise DemoRecordingError(
                f"actor role {role.name!r} runs in container slot "
                f"{role.url_env!r}, which the {_RUNNER_SERVICE!r} service in "
                f"{COMPOSE_PATH.name} does not define."
            ) from None

    def case_roles_for(self, actor_id: str) -> list[CVDRole]:
        """Return the default case roles of the container hosting *actor_id*."""
        return list(self.case_roles.get(urlparse(actor_id).hostname or "", []))


def _service_env(service: object) -> dict[str, str]:
    """Return a compose service's ``environment`` as a mapping.

    Compose accepts a ``KEY=value`` list or a mapping; a service with neither
    has no environment.
    """
    raw = service.get("environment") if isinstance(service, dict) else None
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    env: dict[str, str] = {}
    for item in raw if isinstance(raw, list) else []:
        key, _, value = str(item).partition("=")
        env[key] = value
    return env


def load_topology(compose_path: Path = COMPOSE_PATH) -> ContainerTopology:
    """Read the container layout from the Docker demo's compose file.

    Raises:
        DemoRecordingError: When the compose file lacks the demo runner, its
            CaseActor URL, or a well-formed case-roles setting.
    """
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = compose.get("services") if isinstance(compose, dict) else None
    if not isinstance(services, dict):
        raise DemoRecordingError(
            f"{compose_path.name} has no 'services' mapping."
        )
    if _RUNNER_SERVICE not in services:
        raise DemoRecordingError(
            f"{compose_path.name} has no {_RUNNER_SERVICE!r} service."
        )
    runner_env = _service_env(services[_RUNNER_SERVICE])
    if _CASE_ACTOR_SERVICE_ENV not in runner_env:
        raise DemoRecordingError(
            f"the {_RUNNER_SERVICE!r} service in {compose_path.name} does not "
            f"set {_CASE_ACTOR_SERVICE_ENV}."
        )
    slot_urls = {
        key: value
        for key, value in runner_env.items()
        if key.startswith("VULTRON_") and key.endswith("_BASE_URL")
    }
    case_roles: dict[str, list[CVDRole]] = {}
    for name, service in services.items():
        raw = _service_env(service).get(_CASE_ROLES_ENV)
        if raw is None:
            continue
        try:
            case_roles[name] = [
                CVDRole[value.upper()] for value in json.loads(raw)
            ]
        except (ValueError, KeyError, AttributeError) as exc:
            raise DemoRecordingError(
                f"service {name!r} in {compose_path.name} sets "
                f"{_CASE_ROLES_ENV}={raw!r}, which is not a JSON list of CVD "
                f"role names: {exc}"
            ) from exc
    return ContainerTopology(
        slot_urls=slot_urls,
        case_roles=case_roles,
        case_actor_service_url=runner_env[_CASE_ACTOR_SERVICE_ENV],
    )
