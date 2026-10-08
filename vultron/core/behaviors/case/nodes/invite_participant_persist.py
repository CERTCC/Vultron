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


"""Invitee participant activation leaf node.

Marks the invitee's inert participant record joined when its ``Accept`` of the
stub Invite is processed (CM-11-001, ADR-0114).  The record already exists:
the stub Invite created it at RM.RECEIVED (CM-11-006), and
``InviteeHasParticipantRecordNode`` refuses an Accept that finds none
(CM-11-021).  Composed by ``create_accept_invite_actor_to_case_tree``
(BTND-07-003).
"""

import logging

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.case_participant import CaseParticipant

logger = logging.getLogger(__name__)


class ActivateInviteeParticipantNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Set ``joined=True`` on the invitee's existing participant record.

    A record that is already joined (the backfill-resume path) is left as it
    is.  RM stays at ``RECEIVED``: accepting the stub is joining, not judging
    the case (CM-11-001).
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "new_invite_participant": PortInformation(
            data_type=object, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"new_invite_participant": "/new_invite_participant"}

    def initialise(self) -> None:
        super().initialise()
        try:
            self._participant_bb = self.get_input("new_invite_participant")
        except (NoDataAvailable, NotImplementedError):
            self._participant_bb = None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        participant = self._participant_bb
        if not isinstance(participant, CaseParticipant):
            self.logger.error(
                "%s: participant record not on blackboard for '%s'",
                self.name,
                self.invitee_id,
            )
            return Status.FAILURE
        if not participant.joined:
            participant.joined = True
            self.datalayer.save(participant)
            self.logger.info(
                "%s: promoted inert participant '%s' to joined=True"
                " (ADR-0114, CM-11-006)",
                self.name,
                participant.id_,
            )
        return Status.SUCCESS
