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


"""Whether the case a proposal resolves to was already announced.

The ``Create(VulnerabilityCase)`` answering a proposal takes an id derived
from the CASE_MANAGER and the proposal (:func:`create_case_activity_id`,
OX-06-002), so a redelivered proposal names the activity its first delivery
queued, and the store answers whether the case was announced.  Composed by
``create_case_proposal_received_tree`` (BTND-07-003).
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.case_lookup import CaseIdInputPortMixin
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models._helpers import _as_id
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronProtocolViolationError

logger = logging.getLogger(__name__)


def create_case_activity_id(actor_id: str, proposal_id: str) -> str:
    """The id of the ``Create(VulnerabilityCase)`` answering *proposal_id*.

    Derived from the CASE_MANAGER *actor_id* and the proposal, never minted,
    as the ``Accept`` answering the same proposal is: a redelivered proposal
    rebuilds the Create under the id its first delivery used, so the outbox
    queues it once (OX-06-002) and the store can tell the case was announced
    (CP-05-006, #4146).
    """
    return derived_activity_id("create-case", actor_id, proposal_id)


def announced_case_id(
    datalayer: CasePersistence, actor_id: str, proposal_id: str
) -> str | None:
    """Return the case an earlier delivery of *proposal_id* announced.

    Reads the ``Create(VulnerabilityCase)`` stored under
    :func:`create_case_activity_id`.  Returns ``None`` when nothing is stored
    under that id, i.e. the case was not announced yet.

    Raises:
        VultronProtocolViolationError: something other than a ``Create``
            naming a case is stored under the derived id.  The proposal id is
            the sender's, so a sender that reused it for another proposal
            would otherwise have its new case silently never announced.
    """
    create_id = create_case_activity_id(actor_id, proposal_id)
    stored = datalayer.read(create_id)
    if stored is None:
        return None
    case_id = _as_id(getattr(stored, "context", None))
    if getattr(stored, "type_", None) != "Create" or not case_id:
        raise VultronProtocolViolationError(
            f"'{create_id}' (the Create(VulnerabilityCase) id derived from"
            f" proposal '{proposal_id}') holds a"
            f" {type(stored).__name__} that announces no case"
        )
    return case_id


def case_is_announced(datalayer: CasePersistence, case_id: str) -> bool:
    """Whether a ``Create(VulnerabilityCase)`` for *case_id* is already stored.

    Unlike :func:`announced_case_id`, which asks about one proposal's Create, this
    asks about the case: a proposer that reuses its case under a new proposal id
    (CP-05-008) is answered with a new ``Accept`` but the case is not announced
    to it a second time.
    """
    return any(
        getattr(obj, "type_", None) == "Create"
        and _as_id(getattr(obj, "context", None)) == case_id
        for obj in datalayer.list_objects("Create")
    )


class CheckCaseAlreadyAnnouncedNode(
    CaseIdInputPortMixin, DataLayerConditionWithPorts
):
    """Return SUCCESS if the case on the blackboard was already announced.

    Guards the ``Create(VulnerabilityCase)`` step of the accept flow: when a
    proposer re-proposes a report whose case it already owns and holds
    (CP-05-008), or redelivers a proposal whose act committed (CP-05-006),
    the tree answers with an ``Accept`` naming that case but does not
    announce it a second time.  Returns FAILURE for a case nothing has
    announced yet, so the accept flow announces it.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self._resolve_case_id()
        if case_id is None:
            return Status.FAILURE
        if case_is_announced(self.datalayer, case_id):
            logger.info(
                "%s: case '%s' was already announced — not announcing it"
                " again (CP-05-006, CP-05-008)",
                self.name,
                case_id,
            )
            return Status.SUCCESS
        return Status.FAILURE


__all__ = [
    "CheckCaseAlreadyAnnouncedNode",
    "announced_case_id",
    "case_is_announced",
    "create_case_activity_id",
]
