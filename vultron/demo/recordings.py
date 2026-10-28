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

"""Record every registered demo scenario's case ledgers for the demo UI.

A **recording** is the case ledger a scenario writes when it runs.  Log Replay
in ``ui/`` imports the recordings, so what the audience sees is what Vultron
did (``notes/demo-interactive-ui.md``, decision 2).

Only the CaseActor's ledger, the canonical one, is committed.  Every replica
holds byte-identical copies of the canonical entries (CLP-07-013), so storing
them adds nothing.  Each run still checks that claim: a replica entry that
differs from the canonical entry at its ``logIndex`` fails the recording.

Each scenario runs in this process, through its own ``main()``:

- **Topology.**  Each container slot the scenario's ``ROLES`` name becomes one
  in-process app (:mod:`vultron.demo.in_process`), at the URL the Docker demo
  runner gives that slot.  The URLs and each container's
  ``VULTRON_ACTOR__DEFAULT_CASE_ROLES`` are read from
  ``docker/docker-compose-multi-actor.yml``, so a recording uses the same
  container layout as the Docker demo.  Configuration is process-wide here,
  so the per-container case roles are applied where a proposer states them
  (CP-01-013).
- **Determinism.**  The run's ids and clock are replaced by
  :func:`vultron.demo.determinism.deterministic_run`, seeded with the scenario
  name, and each outbox batch delivers its rows one at a time, so two runs
  give byte-identical recordings.

Output goes to ``ui/src/recordings/<scenario>/case-actor.jsonl``.  The drift test
``test/demo_recordings/test_recordings_drift.py`` fails when a
committed recording differs from a fresh run.

Usage::

    uv run export-demo-recordings                 # every scenario
    uv run export-demo-recordings --scenario rv   # one scenario
    uv run export-demo-recordings --check         # the recorded set only
"""

import asyncio
import contextlib
import importlib
import json
import logging
import os
import shutil
import tempfile
from collections.abc import Awaitable, Callable, Generator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlparse

import click
import yaml
from fastapi.testclient import TestClient

import vultron.demo.utils as demo_utils
from vultron.adapters.driven.datalayer_sqlite import reset_datalayer
from vultron.adapters.driven.trigger_activity_adapter.proposals import (
    _ProposalsMixin,
)
from vultron.adapters.driving.fastapi import outbox_handler
from vultron.adapters.driving.fastapi.outbox_lanes import (
    RowOutcome,
    StallOrder,
)
from vultron.config import config_override
from vultron.demo.determinism import deterministic_run
from vultron.demo.helpers.actor_roles import ActorRole
from vultron.demo.in_process import (
    InProcessRouter,
    create_isolated_actor_app,
    response_value,
)
from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios
from vultron.demo.utils import DataLayerClient
from vultron.enums.roles import CVDRole
from vultron.errors import DemoRecordingError

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORDINGS_DIR = REPO_ROOT / "ui" / "src" / "recordings"
COMPOSE_PATH = REPO_ROOT / "docker" / "docker-compose-multi-actor.yml"

#: The command that regenerates the recordings; named in every drift message.
REGENERATE_COMMAND = "uv run export-demo-recordings"

#: The compose service whose environment maps container slots to URLs.
_RUNNER_SERVICE = "demo-runner"
_CASE_ROLES_ENV = "VULTRON_ACTOR__DEFAULT_CASE_ROLES"
_CASE_ACTOR_SERVICE_ENV = "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL"

RECORDING_SUFFIX = ".jsonl"

#: The dump target whose ledger is the canonical one, and the only one committed.
CANONICAL_ACTOR = "case-actor"


@dataclass(frozen=True)
class ContainerTopology:
    """The Docker demo's container layout, as the recorder needs it.

    Attributes:
        slot_urls: Base URL of each container slot, keyed by the slot's env var
            (``VULTRON_VENDOR_BASE_URL`` → ``http://vendor:7999/api/v2``).
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


def _node_base(url: str) -> str:
    """Return ``scheme://host:port`` of *url*."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


@dataclass
class _Nodes:
    """The entered test clients of one scenario run, keyed by node base."""

    clients: dict[str, TestClient] = field(default_factory=dict)

    def call(
        self, client: DataLayerClient, method: str, path: str, **kwargs: Any
    ) -> Any:
        """Stand in for :meth:`DataLayerClient.call`, routed by host."""
        url = f"{client.base_url}{path}"
        parsed = urlparse(url)
        node = self.clients.get(_node_base(url))
        if node is None:
            raise DemoRecordingError(
                f"no in-process container serves {url!r}; the scenario "
                "addressed a host its ROLES do not name."
            )
        kwargs.pop("timeout", None)
        target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        response = node.request(method.upper(), target, **kwargs)
        return response_value(response, method, url)


def _routed_call(nodes: _Nodes) -> Callable[..., Any]:
    """Return a ``DataLayerClient.call`` replacement that routes via *nodes*.

    A plain function, so it binds the client instance as a method does.
    """

    def call(
        client: DataLayerClient, method: str, path: str, **kwargs: Any
    ) -> Any:
        return nodes.call(client, method, path, **kwargs)

    return call


@contextlib.contextmanager
def _scenario_nodes(
    bases: Sequence[str], topology: ContainerTopology
) -> Generator[_Nodes]:
    """Host one in-process app per node base, with fresh stores.

    Restores the default emitter and drops every cached store on exit, so a
    later run in the same process starts empty.  The router is installed as
    the default emitter because the routes of an isolated app fall back to it.
    """
    reset_datalayer()
    router = InProcessRouter()
    nodes = _Nodes()
    try:
        with (
            config_override(
                VULTRON_DATABASE__DB_URL="sqlite:///:memory:",
                VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL=topology.case_actor_service_url,
            ),
            # Patched on the slot, as its docstring prescribes, so exit puts
            # back exactly what was installed, including nothing at all;
            # `get_default_emitter()` would hand back a fresh adapter instead.
            patch.object(
                outbox_handler._DEFAULT_EMITTER_SLOT, "value", router
            ),
            contextlib.ExitStack() as stack,
        ):
            for base in bases:
                isolated = create_isolated_actor_app(base, router)
                nodes.clients[base] = stack.enter_context(isolated.client)
            yield nodes
    finally:
        reset_datalayer()


def _one_row_at_a_time(
    deliver_batch: Callable[..., Awaitable[list[str]]],
) -> Callable[..., Awaitable[list[str]]]:
    """Wrap the outbox's ``deliver_batch`` so a batch delivers one row at a time.

    The outbox delivers rows for different recipients concurrently
    (OX-01-006), and each in-process delivery runs on a worker thread, so two
    recipients can draw ids in either order and a recording would differ from
    run to run.  One lock per batch makes its rows run in pop order.  The lock
    is the batch's own, so a drain that a delivery causes on another actor
    never waits for it.
    """

    async def serial_deliver_batch(
        rows: list[tuple[str, frozenset[str]]],
        deliver: Callable[[str], Awaitable[RowOutcome]],
        stalled: StallOrder,
    ) -> list[str]:
        lock = asyncio.Lock()

        async def deliver_alone(activity_id: str) -> RowOutcome:
            async with lock:
                return await deliver(activity_id)

        return await deliver_batch(rows, deliver_alone, stalled)

    return serial_deliver_batch


def _read_dump(devlogs: Path, scenario: str) -> dict[str, str]:
    """Return the dumped ledger of each actor in the scenario's manifest.

    Raises:
        DemoRecordingError: When an actor's ledger was not captured.
    """
    manifest = json.loads(
        (devlogs / scenario / "dump-manifest.json").read_text(encoding="utf-8")
    )
    ledgers: dict[str, str] = {}
    for actor in manifest["actors"]:
        if not actor.get("captured") or not actor.get("ledgerFile"):
            raise DemoRecordingError(
                f"scenario {scenario!r}: the ledger of "
                f"{actor.get('actorName')!r} was not captured "
                f"({actor.get('reason') or 'no reason recorded'})."
            )
        ledgers[actor["actorName"]] = (
            devlogs / scenario / actor["ledgerFile"]
        ).read_text(encoding="utf-8")
    return ledgers


def _entries_by_index(actor: str, text: str) -> dict[int, str]:
    """Return each JSONL line of *text* keyed by its entry's ``logIndex``."""
    entries: dict[int, str] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        try:
            entries[json.loads(line)["logIndex"]] = line
        except (ValueError, KeyError, TypeError) as exc:
            raise DemoRecordingError(
                f"the ledger of {actor!r}, line {number}, is not a ledger "
                f"entry with a logIndex: {exc}"
            ) from exc
    return entries


def canonical_ledger(scenario: str, ledgers: dict[str, str]) -> str:
    """Return the canonical ledger of a run, after checking every replica.

    Each replica entry must be byte-identical to the canonical entry at the
    same ``logIndex`` (CLP-07-013).  A replica may hold fewer entries, for
    example a participant that left before the case closed (CM-23-004).

    Raises:
        DemoRecordingError: When the dump holds no canonical ledger, or a
            replica entry is absent from or differs from the canonical one.
    """
    if CANONICAL_ACTOR not in ledgers:
        raise DemoRecordingError(
            f"scenario {scenario!r} dumped no {CANONICAL_ACTOR!r} ledger; "
            f"it dumped {sorted(ledgers)}."
        )
    canonical = _entries_by_index(CANONICAL_ACTOR, ledgers[CANONICAL_ACTOR])
    for actor, text in ledgers.items():
        if actor == CANONICAL_ACTOR:
            continue
        for index, line in _entries_by_index(actor, text).items():
            if canonical.get(index) != line:
                raise DemoRecordingError(
                    f"scenario {scenario!r}: the replica of {actor!r} holds "
                    f"an entry at logIndex {index} that "
                    + (
                        "the canonical ledger does not."
                        if index not in canonical
                        else "differs from the canonical entry."
                    )
                )
    return ledgers[CANONICAL_ACTOR]


def record_scenario(
    spec: ScenarioSpec, topology: ContainerTopology | None = None
) -> str:
    """Run *spec* in this process and return its recording.

    Args:
        spec: The registered scenario to run.
        topology: The container layout; read from the compose file when
            omitted.

    Returns:
        The canonical ledger, as JSONL, once every replica the scenario's
        ledger dump names has been checked against it.

    Raises:
        DemoRecordingError: When the scenario's ROLES name an unknown container
            slot, an actor's ledger is not captured, or a replica disagrees
            with the canonical ledger.
        DemoFailureError: When the scenario itself fails.
    """
    topology = topology or load_topology()
    module = importlib.import_module(spec.module_name)
    roles: list[ActorRole] = module.ROLES
    urls = {role: topology.url_for(role) for role in roles}
    bases = sorted({_node_base(url) for url in urls.values()})
    real_create_case_proposal = _ProposalsMixin.create_case_proposal

    def create_case_proposal(
        self: _ProposalsMixin, actor: str, *args: Any, **kwargs: Any
    ) -> tuple[str, str]:
        # The proposer's own container settings, not this process's (CP-01-013).
        kwargs["proposer_case_roles"] = topology.case_roles_for(actor)
        return real_create_case_proposal(self, actor, *args, **kwargs)

    with tempfile.TemporaryDirectory(prefix="vultron-recording-") as devlogs:
        with (
            deterministic_run(seed=spec.name),
            _scenario_nodes(bases, topology) as nodes,
            patch.dict(os.environ, {"DEVLOGS_DIR": devlogs}),
            patch.object(demo_utils, "DEFAULT_WAIT_SECONDS", 0.0),
            patch.object(
                DataLayerClient,
                "call",
                _routed_call(nodes),
            ),
            patch.object(
                _ProposalsMixin, "create_case_proposal", create_case_proposal
            ),
            patch.object(
                outbox_handler,
                "deliver_batch",
                _one_row_at_a_time(outbox_handler.deliver_batch),
            ),
        ):
            module.main(
                skip_health_check=True,
                **{
                    f"{role.param_stem}_url": url for role, url in urls.items()
                },
            )
        return canonical_ledger(
            spec.name, _read_dump(Path(devlogs), spec.name)
        )


def recording_path(scenario: str) -> Path:
    """Return the committed path of a scenario's recording."""
    return RECORDINGS_DIR / scenario / f"{CANONICAL_ACTOR}{RECORDING_SUFFIX}"


def write_recording(scenario: str, recording: str) -> Path:
    """Replace the committed recording of *scenario* with *recording*.

    Anything else in the scenario's directory is removed with it.
    """
    scenario_dir = RECORDINGS_DIR / scenario
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True)
    path = recording_path(scenario)
    path.write_text(recording, encoding="utf-8")
    return path


def layout_problems(scenario_names: Sequence[str]) -> list[str]:
    """Return how the committed recordings disagree with the registry.

    This checks the part of the recordings the registry decides, which set of
    scenarios is recorded (DEMOCI-11-005), and is cheap enough for pre-commit.
    Whether a recording's content is current takes a run of its scenario, which
    the drift test does.
    """
    registered = set(scenario_names)
    recorded = (
        {path.name for path in RECORDINGS_DIR.iterdir() if path.is_dir()}
        if RECORDINGS_DIR.is_dir()
        else set()
    )
    problems = [
        f"{name}: registered but not recorded"
        for name in sorted(registered - recorded)
    ]
    problems += [
        f"{name}: recorded but not a registered scenario"
        for name in sorted(recorded - registered)
    ]
    expected = f"{CANONICAL_ACTOR}{RECORDING_SUFFIX}"
    for name in sorted(registered & recorded):
        held = sorted(path.name for path in (RECORDINGS_DIR / name).iterdir())
        if expected not in held:
            problems.append(f"{name}: has no {expected}")
        if extra := [held_name for held_name in held if held_name != expected]:
            problems.append(
                f"{name}: holds files other than {expected}: {extra}"
            )
    return problems


@click.command(name="export-demo-recordings")
@click.option(
    "--scenario",
    "scenarios",
    multiple=True,
    help="Record only this scenario (repeatable). Default: every scenario.",
)
@click.option(
    "--check",
    is_flag=True,
    help="Run nothing; fail when the set of recorded scenarios is not the "
    "registry's.",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="ERROR",
    show_default=True,
    help="Log level of the scenario runs. Below ERROR, the in-process "
    "harness's known shared-store warnings are shown too.",
)
def main(scenarios: tuple[str, ...], check: bool, log_level: str) -> None:
    """Record every registered demo scenario into ui/src/recordings/."""
    logging.basicConfig(level=log_level)
    specs = {spec.name: spec for spec in discover_scenarios()}
    if check:
        if scenarios:
            raise click.UsageError(
                "--check compares the whole recorded set with the registry; "
                "it takes no --scenario."
            )
        _check_layout(tuple(specs))
        return
    unknown = sorted(set(scenarios) - set(specs))
    if unknown:
        raise click.BadParameter(
            f"not registered: {', '.join(unknown)}", param_hint="--scenario"
        )
    if not scenarios:
        _remove_unregistered(set(specs))
    topology = load_topology()
    for name in scenarios or tuple(specs):
        path = write_recording(name, record_scenario(specs[name], topology))
        click.echo(f"Wrote {path.relative_to(REPO_ROOT)}")


def _check_layout(scenario_names: Sequence[str]) -> None:
    """Report each layout problem; exit 1 when there is one."""
    problems = layout_problems(scenario_names)
    for problem in problems:
        click.echo(f"ui/src/recordings/{problem}", err=True)
    if problems:
        click.echo(f"Regenerate with: {REGENERATE_COMMAND}", err=True)
        raise SystemExit(1)


def _remove_unregistered(registered: set[str]) -> None:
    """Drop the recordings of scenarios no longer registered (a full run)."""
    for stale in sorted(RECORDINGS_DIR.glob("*/")):
        if stale.name not in registered:
            shutil.rmtree(stale)
            click.echo(f"Removed {stale.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
