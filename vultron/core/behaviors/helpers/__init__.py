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

"""DataLayer-aware behavior tree helper nodes.

Base classes and common nodes for BT implementations that interact with the
DataLayer for persistent state access, grouped by concern:

- ``messages``: feedback a node sets when composed without a dependency
- ``rm_states``: read a participant's RM states or signal FAILURE
- ``case_resolution``: the case-resolution disposition policy (ADR-0087)
- ``base``: blackboard-client base classes
- ``ports_base``: typed-Ports base classes (BTND-03-009 through BTND-03-011)
- ``emit``: the shared outbox-enqueue seam (OX-14-001)
- ``participant_lookup``: resolve a case participant by actor ID
- ``object_nodes``: generic read, update and create nodes
"""

# PortInformation is py_trees' port declaration type; behaviors modules have
# imported it from here since the typed-Ports migration, so it stays a public
# name of this package (CS-18-003).
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers.base import (
    DataLayerAction,
    DataLayerCondition,
)
from vultron.core.behaviors.helpers.case_resolution import (
    require_case,
    resolve_case_replica,
)
from vultron.core.behaviors.helpers.emit import UpdateActorOutbox
from vultron.core.behaviors.helpers.messages import (
    ACTIVITY_UNAVAILABLE,
    DATALAYER_OR_ACTOR_UNAVAILABLE,
    DATALAYER_UNAVAILABLE,
    TRIGGER_FACTORY_UNAVAILABLE,
    WIRE_RENDER_PORT_UNAVAILABLE,
    WIRING_UNAVAILABLE_MESSAGES,
)
from vultron.core.behaviors.helpers.object_nodes import (
    CreateObject,
    ReadObject,
    UpdateObject,
)
from vultron.core.behaviors.helpers.participant_lookup import (
    FindParticipantByActorIdNode,
)
from vultron.core.behaviors.helpers.ports_base import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.helpers.rm_states import read_rm_states

__all__ = [
    "ACTIVITY_UNAVAILABLE",
    "DATALAYER_OR_ACTOR_UNAVAILABLE",
    "DATALAYER_UNAVAILABLE",
    "TRIGGER_FACTORY_UNAVAILABLE",
    "WIRE_RENDER_PORT_UNAVAILABLE",
    "WIRING_UNAVAILABLE_MESSAGES",
    "CreateObject",
    "DataLayerAction",
    "DataLayerActionWithPorts",
    "DataLayerCondition",
    "DataLayerConditionWithPorts",
    "FindParticipantByActorIdNode",
    "PortInformation",
    "ReadObject",
    "UpdateActorOutbox",
    "UpdateObject",
    "read_rm_states",
    "require_case",
    "resolve_case_replica",
]
