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

"""Run one scenario in this process, one isolated app per container slot."""

import asyncio
import contextlib
import importlib
import os
import tempfile
from collections.abc import Awaitable, Callable, Generator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlparse

import py_trees
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
from vultron.demo.determinism import (
    TREE_RECORDING_SEED,
    deterministic_run,
)
from vultron.demo.helpers.actor_roles import ActorRole
from vultron.demo.in_process import (
    InProcessRouter,
    create_isolated_actor_app,
    response_value,
)
from vultron.demo.recordings.layout import Recording
from vultron.demo.recordings.ledgers import (
    canonical_ledger,
    read_dump,
    read_step_marks,
)
from vultron.demo.recordings.topology import ContainerTopology, load_topology
from vultron.demo.scenario.registry import ScenarioSpec
from vultron.demo.utils import DataLayerClient
from vultron.errors import DemoRecordingError


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

    The py_trees blackboard registry is cleared too.  It is process-global and
    keyed by a uuid4 that nothing unregisters, so once every scenario records
    with one tree-wide seed (DEMOCI-11-025) the second run in a process redraws
    the first run's client ids and py_trees refuses the registration with
    "this unique identifier has already been registered".
    """
    reset_datalayer()
    py_trees.blackboard.Blackboard.clear()
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
        py_trees.blackboard.Blackboard.clear()


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


def record_scenario(
    spec: ScenarioSpec, topology: ContainerTopology | None = None
) -> Recording:
    """Run *spec* in this process and return its recording.

    Args:
        spec: The registered scenario to run.
        topology: The container layout; read from the compose file when
            omitted.

    Returns:
        The canonical ledger, as JSONL, once every replica the scenario's
        ledger dump names has been checked against it, and the ledger tail at
        each declared step of its path.

    Raises:
        DemoRecordingError: When the scenario's ROLES name an unknown container
            slot, an actor's ledger is not captured, a replica disagrees
            with the canonical ledger, or the run did not mark every declared
            step of its path, in order and within the ledger.
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
            # One seed for the whole tree, not this scenario's name, so
            # siblings draw the same ids for a shared opening
            # (DEMOCI-11-025, DEMOCI-11-018).
            deterministic_run(seed=TREE_RECORDING_SEED),
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
        ledger = canonical_ledger(
            spec.name, read_dump(Path(devlogs), spec.name)
        )
        steps = read_step_marks(Path(devlogs), spec.name, spec.path)
    return Recording(spec.name, ledger=ledger, steps=steps)
