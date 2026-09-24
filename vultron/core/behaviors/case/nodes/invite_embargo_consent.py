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


"""Embargo-consent leaf nodes for the accept-invite tree.

Check whether the case embargo is EM.ACTIVE and, if so, sign the invitee's
consent (CM-10-001). Composed by the ``MaybeSignEmbargoConsentNode``
one-off composite retained in ``accept_invite_tree.py`` (BTND-07-003).
"""

import logging

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger

logger = logging.getLogger(__name__)


class _CheckEmbargoActiveStateNode(DataLayerActionWithPorts):
    """Return SUCCESS iff the case has an active embargo in EM.ACTIVE state."""

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "invitee_case": PortInformation(data_type=object, required=False),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "active_embargo_id": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "invitee_case": "/invitee_case",
            "active_embargo_id": "/active_embargo_id",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self._invitee_case_bb = self.get_input("invitee_case")
        except (NoDataAvailable, NotImplementedError):
            self._invitee_case_bb = None

    def update(self) -> Status:
        case = self._invitee_case_bb
        if case is None:
            self.logger.error("%s: invitee_case not available", self.name)
            # Initialize key so downstream nodes can safely read it.
            self._set_output("active_embargo_id", None)
            return Status.FAILURE

        active_embargo_id = _as_id(case.active_embargo)
        em_state = case.current_status.em.state
        if active_embargo_id and em_state == EM.ACTIVE:
            self._set_output("active_embargo_id", active_embargo_id)
            return Status.SUCCESS
        # Always write the key so PersistInviteeParticipantNode can read it
        # even when there is no active embargo (py_trees raises KeyError for
        # unwritten READ-registered keys — see AGENTS.md pitfalls).
        self._set_output("active_embargo_id", None)
        return Status.FAILURE


class _SignEmbargoConsentLeafNode(DataLayerActionWithPorts):
    """Sign embargo consent on the participant and record the event."""

    def __init__(self, invitee_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invitee_id = invitee_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "new_invite_participant": PortInformation(
            data_type=object, required=True
        ),
        "active_embargo_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "new_invite_participant": "/new_invite_participant",
            "active_embargo_id": "/active_embargo_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.new_invite_participant = self.get_input("new_invite_participant")
        self.active_embargo_id: str = self.get_input("active_embargo_id")

    def update(self) -> Status:
        participant = self.new_invite_participant
        active_embargo_id = self.active_embargo_id
        if not isinstance(participant, VultronParticipant) or not isinstance(
            active_embargo_id, str
        ):
            self.logger.error(
                "%s: participant or active_embargo_id missing", self.name
            )
            return Status.FAILURE

        if active_embargo_id not in participant.accepted_embargo_ids:
            participant.accepted_embargo_ids.append(active_embargo_id)
        if participant.embargo_consent_state not in (
            PEC.SIGNATORY,
            PEC.DECLINED,
        ):
            participant.apply_pec_transition(PEC_Trigger.ACCEPT)
        self.logger.info(
            "%s: signed embargo consent for invitee '%s' (EM.ACTIVE,"
            " CM-10-001)",
            self.name,
            self.invitee_id,
        )
        return Status.SUCCESS
