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

"""The CASE_MANAGER's EMB-17-003 re-invite of a late accepter (EMB-17-011).

A late ``Accept`` names an embargo that is no longer the case's current one,
so the manager asks the accepter again about the current embargo.  The frame is
the relay's (:class:`~vultron.core.behaviors.embargo.nodes.relay.RelayEmbargoInviteToEachNode`),
narrowed to one fixed recipient and committed under an event type of its own.
"""

from typing import TYPE_CHECKING

from vultron.core.behaviors.embargo.nodes.relay import (
    RelayEmbargoInviteToEachNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models.rsvp_deadline import EMBARGO_REINVITE_EVENT_TYPE

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig


class ReinviteStaleAccepterNode(RelayEmbargoInviteToEachNode):
    """Commit and send the CASE_MANAGER's EMB-17-003 re-invite of one accepter.

    A late ``Accept`` named an embargo that is no longer the case's current
    one, so the manager asks the accepter again about the current embargo
    (EMB-17-003).  The frame is the relay's — stamp a fresh deadline (ASK-03-004,
    CM-28-012), build, commit before the outbox write, queue, apply PEC
    ``INVITE`` and record the deadline (CM-18-003, CM-28-013) — with two
    differences: the Invite is the manager's own ask, so it has no
    ``attributedTo``, and it is committed under
    :data:`~vultron.core.models.rsvp_deadline.EMBARGO_REINVITE_EVENT_TYPE`, so
    a replica replays the invitee's record and never re-adjudicates a proposal
    (EP-09-007, RSH-08-004).  The recipient and embargo are fixed at
    construction; the collect node and the recipients key are not used.
    """

    _EVENT_TYPE = EMBARGO_REINVITE_EVENT_TYPE

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        invitee_id: str,
        name: str | None = None,
        actor_config: "ActorConfig | None" = None,
    ) -> None:
        # No proposer: ``_attributed_to`` answers ``None``.
        super().__init__(
            case_id=case_id,
            embargo_id=embargo_id,
            proposer_id="",
            name=name or self.__class__.__name__,
            actor_config=actor_config,
        )
        self._invitee_id = invitee_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"sync_port": "/sync_port"}

    def _load_relay_inputs(self) -> None:
        self._recipients = [self._invitee_id]

    def _attributed_to(self) -> str | None:
        return None


__all__ = ["ReinviteStaleAccepterNode"]
