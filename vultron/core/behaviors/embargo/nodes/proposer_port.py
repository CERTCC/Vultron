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

"""Whose terms an embargo proposal carries, published for the adjudication.

The CASE_MANAGER adjudicating a proposal records the *proposer's* consent to
its terms (ADR-0093), leaves the proposer out of the relay (EP-09-002) and
skips its own row when it is the proposer (EP-09-024).  The nodes that do
so, shared by the received and the trigger proposal trees, read the
proposer from the ``embargo_proposer_id`` port.  :class:`PublishEmbargoProposerNode`
writes it, in the tree, so no handler reads the store to find it (CM-24-002,
ADR-0195).
"""

import logging
from typing import cast

from py_trees.common import Status
from py_trees.ports import BehaviourWithPorts, PortInformation

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.participants.role_predicate import has_role
from vultron.core.ports.case_persistence import CasePersistence
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)

#: The port the proposer is published on and read from.
EMBARGO_PROPOSER_KEY = "embargo_proposer_id"

#: The input port a node reading the proposer declares.
EMBARGO_PROPOSER_INPUT: dict[str, PortInformation] = {
    EMBARGO_PROPOSER_KEY: PortInformation(data_type=str, required=True),
}

#: The remapping a node reading or writing the proposer declares.
EMBARGO_PROPOSER_REMAPPING: dict[str, str] = {
    EMBARGO_PROPOSER_KEY: f"/{EMBARGO_PROPOSER_KEY}",
}


def read_embargo_proposer(node: BehaviourWithPorts) -> str:
    """The proposer an earlier node of the run published.

    Raises:
        NoDataAvailable: Nothing published it: the tree was composed
            without :class:`PublishEmbargoProposerNode`, a wiring fault.
    """
    return cast(str, node.get_input(EMBARGO_PROPOSER_KEY))


def embargo_proposer(
    datalayer: CasePersistence,
    *,
    sender_id: str,
    attributed_to: str | None,
    case_id: str,
    activity_id: str,
) -> str:
    """The actor whose terms a proposal carries.

    The proposal's ``actor`` (*sender_id*), or its ``attributedTo`` when the
    proposal was itself relayed, since a relayed Invite is sent as the
    CASE_MANAGER with the proposer attributed (CM-24-001, CM-24-002).

    Only a relay may attribute: *attributed_to* is honoured when the sender
    is the case's CASE_MANAGER, as
    :func:`~vultron.core.participants.role_predicate.has_role` answers it
    (ARCH-24-008), and ignored otherwise — including for a second
    participant the roster also records with the role — so a participant
    cannot have a third party's consent recorded, or that party left out of
    the Invites, by naming it on its own proposal (PCR-08-010).

    *activity_id* names the proposal in the warnings.
    """
    if not attributed_to:
        return sender_id
    # The one source of "is the sender the case's authority" (ARCH-24-008):
    # ``False`` when this store holds no such case, so the sender is then
    # the proposer.  The roster and the sender id are both canonical
    # (OID-01-006, OID-01-007, #5919).
    if has_role(sender_id, case_id, CVDRole.CASE_MANAGER, datalayer):
        return attributed_to
    logger.warning(
        "embargo proposal '%s' from '%s' attributes its proposal to '%s', but"
        " only the case's CASE_MANAGER relays — treating the sender as the"
        " proposer",
        activity_id,
        sender_id,
        attributed_to,
    )
    return sender_id


class PublishEmbargoProposerNode(DataLayerConditionWithPorts):
    """Publish whose terms the proposal carries, for the adjudication.

    Always SUCCESS: the proposer is a fact the adjudication reads, not a
    verdict.  With no *attributed_to* the sender is the proposer, as on the
    trigger side, where the executing actor proposes its own terms.

    Args:
        sender_id: The proposal's ``actor``.
        case_id: The case the proposal is for.
        activity_id: The proposal, for the logs.
        attributed_to: The proposal's ``attributedTo`` in its canonical
            spelling (OID-01-006), or ``None`` when it names none.
    """

    OUTPUT_PORTS: dict[str, PortInformation] = {
        EMBARGO_PROPOSER_KEY: PortInformation(data_type=str, required=True),
    }

    def __init__(
        self,
        sender_id: str,
        case_id: str,
        activity_id: str,
        *,
        attributed_to: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sender_id = sender_id
        self._case_id = case_id
        self._activity_id = activity_id
        self._attributed_to = attributed_to
        self.proposer_id: str | None = None

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return dict(EMBARGO_PROPOSER_REMAPPING)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        self.proposer_id = embargo_proposer(
            self.datalayer,
            sender_id=self._sender_id,
            attributed_to=self._attributed_to,
            case_id=self._case_id,
            activity_id=self._activity_id,
        )
        self._set_output(EMBARGO_PROPOSER_KEY, self.proposer_id)
        self.feedback_message = f"the proposer is '{self.proposer_id}'"
        return Status.SUCCESS


__all__ = [
    "EMBARGO_PROPOSER_INPUT",
    "EMBARGO_PROPOSER_KEY",
    "EMBARGO_PROPOSER_REMAPPING",
    "PublishEmbargoProposerNode",
    "embargo_proposer",
    "read_embargo_proposer",
]
