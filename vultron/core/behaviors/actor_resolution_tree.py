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
"""The one-tick tree that asks ResolveActorDetails and keeps its record.

:func:`create_actor_resolution_tree` runs the actor-resolution call-out and,
when it answers *yes*, copies the record it wrote to the
``resolved_actor`` output port into a dict the caller holds, while the tree
still runs.  The caller reads that dict, never the blackboard, after the run
(BTBridge restores execution-scoped keys when it returns).

References
----------
- Spec: ``specs/actor-knowledge-model.yaml`` AKM-05-002;
  ``specs/behavior-tree-node-design.yaml`` BTND-03-021
"""

from __future__ import annotations

from typing import Final

import py_trees
from py_trees.common import Status
from py_trees.ports import BehaviourWithPorts, PortInformation

from vultron.core.behaviors.call_out.capabilities.actor_resolution import (
    RESOLVED_ACTOR_KEY,
)
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory
from vultron.core.behaviors.helpers.ports_base import _OptionalPortRead
from vultron.core.behaviors.node_logger import port_wiring_logger
from vultron.core.models.actor import CoreActor

#: The node name a tree passes to the actor-resolution backend factory.
RESOLVE_ACTOR_DETAILS: Final[str] = "ResolveActorDetails"


class KeepResolvedActorNode(_OptionalPortRead, BehaviourWithPorts):
    """Copy the record on ``resolved_actor`` into the caller's dict.

    It reads no store, so it takes only the shared optional-port read, not
    a DataLayer base.  Reads the port as optional: a backend that answers *yes* without writing
    it (one that binds no declaration) leaves the dict empty.  A value that
    is not a :class:`~vultron.core.models.actor.CoreActor` raises
    ``TypeError`` and fails the whole run (BTND-03-021).

    Args:
        kept: The caller's dict; the record goes in under
            ``resolved_actor``.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        RESOLVED_ACTOR_KEY: PortInformation(
            data_type=CoreActor, required=False
        ),
    }
    OUTPUT_PORTS: dict[str, PortInformation] = {}

    def __init__(self, kept: dict[str, CoreActor]) -> None:
        super().__init__(name=type(self).__name__)
        self._kept = kept

    def setup(self, **kwargs: object) -> None:
        self.setup_ports(
            port_remappings={RESOLVED_ACTOR_KEY: f"/{RESOLVED_ACTOR_KEY}"},
            logger=port_wiring_logger(),
        )

    def update(self) -> Status:
        record = self._try_get_input(RESOLVED_ACTOR_KEY)
        if isinstance(record, CoreActor):
            self._kept[RESOLVED_ACTOR_KEY] = record
        return Status.SUCCESS


def create_actor_resolution_tree(
    resolve_actor_factory: CallOutBackendFactory,
    kept: dict[str, CoreActor],
) -> py_trees.behaviour.Behaviour:
    """Ask ResolveActorDetails, then keep its record in *kept* on *yes*.

    The run's blackboard carries the peer's URI on ``peer_actor_id`` and the
    acting actor on ``actor_id``; the caller clears ``resolved_actor`` for
    the run, so a record left by an earlier run is never kept.
    """
    return py_trees.composites.Sequence(
        name="ResolveAndKeepActorDetails",
        memory=False,
        children=[
            resolve_actor_factory(RESOLVE_ACTOR_DETAILS),
            KeepResolvedActorNode(kept),
        ],
    )


__all__ = [
    "KeepResolvedActorNode",
    "RESOLVE_ACTOR_DETAILS",
    "create_actor_resolution_tree",
]
