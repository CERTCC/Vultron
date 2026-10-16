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

Check whether the case has an embargo in force (EM ``ACTIVE`` or
``REVISE``) and, if so, sign the invitee's consent to it (CM-10-001).
Composed by the ``MaybeSignEmbargoConsentNode`` one-off composite retained
in ``accept_invite_tree.py`` (BTND-07-003).
"""

import logging

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants.stub_reply import stub_accept_consent

logger = logging.getLogger(__name__)


class _CheckEmbargoActiveStateNode(DataLayerActionWithPorts):
    """Return SUCCESS iff the case has an embargo in force.

    In force means the case carries an active embargo — EM ``ACTIVE``, or
    ``REVISE`` while a revision is open and the prior terms still hold.  The
    same fact :meth:`VulnerabilityCase.is_active_participant` keys on, so a
    joiner that accepts during a revision signs the terms in force and is
    active (CM-10-004); signing only at ``ACTIVE`` would leave it inert
    under terms that still hold.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "invitee_case": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"invitee_case": "/invitee_case"}

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
            return Status.FAILURE
        return (
            Status.SUCCESS if _as_id(case.active_embargo) else Status.FAILURE
        )


class _SignEmbargoConsentLeafNode(DataLayerActionWithPorts, StateWriteCapable):
    """Write the invitee's agreement its ``Accept`` of the stub Invite states.

    The Accept's own entry, committed by intake, is the entry for the row
    (CLP-07-013): the row is written through the one apply function, as a
    replica writes it from the same entry
    (:func:`~vultron.core.participants.stub_reply.stub_accept_consent`,
    ADR-0124).  The changed record replaces ``new_invite_participant`` for
    the nodes that persist it.
    """

    def __init__(self, invitee_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invitee_id = invitee_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "new_invite_participant": PortInformation(
            data_type=object, required=True
        ),
        "invitee_case": PortInformation(data_type=object, required=False),
    }

    #: Written back to the record's own key, so the nodes that persist it
    #: read the signed copy.
    OUTPUT_PORTS: dict[str, PortInformation] = {
        "signed_participant": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "new_invite_participant": "/new_invite_participant",
            "invitee_case": "/invitee_case",
            "signed_participant": "/new_invite_participant",
        }

    def initialise(self) -> None:
        super().initialise()
        self.new_invite_participant = self.get_input("new_invite_participant")
        try:
            self._invitee_case = self.get_input("invitee_case")
        except (NoDataAvailable, NotImplementedError):
            self._invitee_case = None

    def update(self) -> Status:
        participant = self.new_invite_participant
        case = self._invitee_case
        if not isinstance(participant, CaseParticipant) or not isinstance(
            case, VulnerabilityCase
        ):
            self.logger.error(
                "%s: participant or invitee_case missing", self.name
            )
            return Status.FAILURE

        # An AGREED row stays; a participant that declined this embargo is
        # not signed (ADR-0118).
        signed = stub_accept_consent(case, participant)
        self._set_output("signed_participant", signed)
        self.logger.info(
            "%s: %s embargo consent for invitee '%s' (embargo in force,"
            " CM-10-001)",
            self.name,
            "recorded" if signed is not participant else "no change to",
            self.invitee_id,
        )
        return Status.SUCCESS
