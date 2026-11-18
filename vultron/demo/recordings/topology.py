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
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml

from vultron.config import AppConfig
from vultron.demo.helpers.actor_roles import ActorRole
from vultron.demo.in_process import node_app_config
from vultron.enums.roles import CVDRole
from vultron.errors import DemoRecordingError
from vultron.primitives import require_non_empty

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_PATH = REPO_ROOT / "docker" / "docker-compose-multi-actor.yml"

#: The compose service that drives a scenario; its environment maps container
#: slots to URLs.
RUNNER_SERVICE = "demo-runner"
_CASE_ROLES_ENV = "VULTRON_ACTOR__DEFAULT_CASE_ROLES"
_CASE_ACTOR_SERVICE_ENV = "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL"
_SERVER_BASE_URL_ENV = "VULTRON_SERVER__BASE_URL"
_LOG_LEVEL_ENV = "VULTRON_SERVER__LOG_LEVEL"

#: The ``AppConfig`` settings a compose service may set that an in-process
#: node does not take from it, each with the reason.  Every other
#: ``AppConfig`` setting a service sets is carried into that node's config
#: (:meth:`ContainerTopology.config_for`), and a setting in neither list is
#: refused, so a new per-container setting cannot silently stay shared.
NOT_CARRIED_IN_PROCESS: dict[str, str] = {
    "VULTRON_DATABASE__DB_URL": (
        "an in-process node already has its own in-memory storage deployment "
        "(vultron.demo.in_process.node_db_url), the stand-in for the volume"
    ),
    _LOG_LEVEL_ENV: (
        "one process has one root logger, so the services must all set the "
        "same level, which load_topology() checks"
    ),
}

#: The ``AppConfig`` settings an in-process node takes from its service.
CARRIED_IN_PROCESS: frozenset[str] = frozenset(
    {_SERVER_BASE_URL_ENV, _CASE_ROLES_ENV, _CASE_ACTOR_SERVICE_ENV}
)

#: Environment variables a service sets that are not ``AppConfig`` settings.
_NOT_APP_CONFIG = frozenset(
    {"PYTHONPATH", "VULTRON_ACTOR_ID", "VULTRON_SEED_CONFIG"}
)


@dataclass(frozen=True)
class ContainerSettings:
    """The per-container ``AppConfig`` settings one compose service sets.

    Attributes:
        base_url: Its ``VULTRON_SERVER__BASE_URL``, or ``None`` when unset.
        case_actor_service_url: Its ``VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL``,
            or ``None`` when unset.
    """

    base_url: str | None = None
    case_actor_service_url: str | None = None

    def __post_init__(self) -> None:
        """Refuse a blank setting: if present, then non-empty (CS-08-002)."""
        if self.base_url is not None:
            require_non_empty(self.base_url, "base_url")
        if self.case_actor_service_url is not None:
            require_non_empty(
                self.case_actor_service_url, "case_actor_service_url"
            )


@dataclass(frozen=True)
class ContainerTopology:
    """The Docker demo's container layout, as the recorder needs it.

    Attributes:
        slot_urls: Base URL of each cast container, keyed by the slot's env
            var (``VULTRON_ACTOR1_BASE_URL`` → ``http://actor1:7999/api/v2``).
        case_roles: Each container's ``VULTRON_ACTOR__DEFAULT_CASE_ROLES``,
            keyed by host name.  A container without the setting is absent.
        settings: Every service's other per-container settings, keyed by
            host name, so a service that sets none of them is still present.
    """

    slot_urls: dict[str, str]
    case_roles: dict[str, list[CVDRole]]
    settings: dict[str, ContainerSettings] = field(default_factory=dict)

    def url_for(self, role: ActorRole) -> str:
        """Return the base URL of the container slot *role* runs in."""
        try:
            return self.slot_urls[role.url_env]
        except KeyError:
            raise DemoRecordingError(
                f"actor role {role.name!r} runs in container slot "
                f"{role.url_env!r}, which the {RUNNER_SERVICE!r} service in "
                f"{COMPOSE_PATH.name} does not define."
            ) from None

    def case_roles_for(self, actor_id: str) -> list[CVDRole]:
        """Return the default case roles of the container hosting *actor_id*."""
        return list(self.case_roles.get(urlparse(actor_id).hostname or "", []))

    def config_for(self, url: str, base: AppConfig) -> AppConfig:
        """Return the ``AppConfig`` of the container serving *url* (ADR-0206).

        It is *base* with the container's own settings: its server base URL
        when it sets one, and its default case roles and CaseActor service
        URL, each the ``AppConfig`` default when the service does not set
        it.  So a container that declares no case roles gets none, as in
        Docker, whatever *base* holds.

        Args:
            url: Any URL on the container, such as its base URL or an actor
                id it hosts; its host name names the compose service.
            base: The config the container's settings are applied to, such
                as the process-wide config of the run.

        Raises:
            DemoRecordingError: When no compose service is named by the host
                of *url*.
        """
        host = urlparse(url).hostname or ""
        own = self.settings.get(host)
        if own is None:
            raise DemoRecordingError(
                f"{url!r} names host {host!r}, which is no service in "
                f"{COMPOSE_PATH.name}."
            )
        return node_app_config(
            base,
            case_actor_service_url=own.case_actor_service_url,
            base_url=own.base_url,
            default_case_roles=self.case_roles_for(url),
        )

    def runner_config(self, base: AppConfig) -> AppConfig:
        """Return the ``AppConfig`` of the service that drives a scenario."""
        return self.config_for(f"http://{RUNNER_SERVICE}", base)


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
    if RUNNER_SERVICE not in services:
        raise DemoRecordingError(
            f"{compose_path.name} has no {RUNNER_SERVICE!r} service."
        )
    runner_env = _service_env(services[RUNNER_SERVICE])
    if _CASE_ACTOR_SERVICE_ENV not in runner_env:
        raise DemoRecordingError(
            f"the {RUNNER_SERVICE!r} service in {compose_path.name} does not "
            f"set {_CASE_ACTOR_SERVICE_ENV}."
        )
    slot_urls = {
        key: value
        for key, value in runner_env.items()
        if key.startswith("VULTRON_") and key.endswith("_BASE_URL")
    }
    case_roles: dict[str, list[CVDRole]] = {}
    settings: dict[str, ContainerSettings] = {}
    for name, service in services.items():
        env = _service_env(service)
        _refuse_uncarried_settings(name, env, compose_path)
        _refuse_empty_carried_settings(name, env, compose_path)
        settings[name] = ContainerSettings(
            base_url=env.get(_SERVER_BASE_URL_ENV),
            case_actor_service_url=env.get(_CASE_ACTOR_SERVICE_ENV),
        )
        raw = env.get(_CASE_ROLES_ENV)
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
    _refuse_differing_log_levels(services, compose_path)
    return ContainerTopology(
        slot_urls=slot_urls,
        case_roles=case_roles,
        settings=settings,
    )


def _refuse_empty_carried_settings(
    name: str, env: dict[str, str], compose_path: Path
) -> None:
    """Refuse a carried setting set to an empty value (CS-08-002).

    Raises:
        DemoRecordingError: When the service sets a setting in
            :data:`CARRIED_IN_PROCESS` to an empty or blank value.
    """
    empty = sorted(
        key
        for key in CARRIED_IN_PROCESS
        if key in env and not env[key].strip()
    )
    if empty:
        raise DemoRecordingError(
            f"service {name!r} in {compose_path.name} sets {empty} to an "
            "empty value; leave a setting out rather than set it empty."
        )


def _refuse_uncarried_settings(
    name: str, env: dict[str, str], compose_path: Path
) -> None:
    """Refuse a service setting no in-process node would take or skip.

    Raises:
        DemoRecordingError: When the service sets an ``AppConfig`` setting
            (a ``VULTRON_`` variable with a ``__`` section delimiter, or a
            top-level one) in neither :data:`CARRIED_IN_PROCESS` nor
            :data:`NOT_CARRIED_IN_PROCESS`.
    """
    unknown = sorted(
        key
        for key in env
        if key.startswith("VULTRON_")
        and key not in _NOT_APP_CONFIG
        and key not in CARRIED_IN_PROCESS
        and key not in NOT_CARRIED_IN_PROCESS
        and not (key.endswith("_BASE_URL") and "__" not in key)
    )
    if unknown:
        raise DemoRecordingError(
            f"service {name!r} in {compose_path.name} sets {unknown}, which "
            "an in-process node neither carries into its own config nor "
            "lists as skipped; add each to CARRIED_IN_PROCESS (and to "
            "ContainerTopology.config_for) or to NOT_CARRIED_IN_PROCESS."
        )


def _refuse_differing_log_levels(
    services: dict[str, object], compose_path: Path
) -> None:
    """Refuse services that set different log levels.

    In process every node shares one root logger, so a per-container level
    cannot be carried (:data:`NOT_CARRIED_IN_PROCESS`).  That skip is only
    sound while the services agree.

    Raises:
        DemoRecordingError: When two services set
            ``VULTRON_SERVER__LOG_LEVEL`` to different values.
    """
    levels = {
        name: env[_LOG_LEVEL_ENV]
        for name, service in services.items()
        if _LOG_LEVEL_ENV in (env := _service_env(service))
    }
    if len(set(levels.values())) > 1:
        raise DemoRecordingError(
            f"services in {compose_path.name} set {_LOG_LEVEL_ENV} to "
            f"different values {levels}; one in-process root logger cannot "
            "hold more than one level."
        )
