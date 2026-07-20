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

"""BT leaf nodes for received Add/Remove CaseParticipant activities.

Provides action nodes that apply participant membership changes to a
``VulnerabilityCase`` in the DataLayer.

Composite tree factories assembling these nodes are in
``case_participant_received_tree.py`` at the process-area root per
BTND-07-003.
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant


class AddCaseParticipantToCaseReceivedNode(DataLayerAction):
    """Add a participant to a case and persist the updated case.

    Reads both the participant and the case from the DataLayer, calls
    ``case.add_participant(participant)``, and saves the updated case.

    Returns ``SUCCESS`` when the participant is added, ``FAILURE`` when
    either the case or participant cannot be found.
    """

    def __init__(
        self,
        participant_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.participant_id = participant_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        participant = self.datalayer.read(self.participant_id)
        case = self.datalayer.read(self.case_id)

        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = f"case '{self.case_id}' not found"
            self.logger.warning(
                "%s: case '%s' not found",
                self.name,
                self.case_id,
            )
            return Status.FAILURE

        if not isinstance(participant, CaseParticipant):
            self.feedback_message = (
                f"participant '{self.participant_id}' not found"
            )
            self.logger.warning(
                "%s: participant '%s' not found",
                self.name,
                self.participant_id,
            )
            return Status.FAILURE

        case.add_participant(participant)
        self.datalayer.save(case)
        self.logger.info(
            "%s: added participant '%s' to case '%s'",
            self.name,
            self.participant_id,
            self.case_id,
        )
        return Status.SUCCESS


class RemoveCaseParticipantFromCaseReceivedNode(DataLayerAction):
    """Remove a participant from a case and persist the updated case.

    Reads the case from the DataLayer and calls
    ``case.remove_participant(participant_id)``.  Idempotent: if the
    participant is not present in the case, returns ``SUCCESS`` without
    mutation.

    Returns ``SUCCESS`` when the participant is absent or removed,
    ``FAILURE`` when the case cannot be found.
    """

    def __init__(
        self,
        participant_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.participant_id = participant_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)

        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = f"case '{self.case_id}' not found"
            self.logger.warning(
                "%s: case '%s' not found",
                self.name,
                self.case_id,
            )
            return Status.FAILURE

        existing_ids = [_as_id(p) for p in case.case_participants]
        if self.participant_id not in existing_ids:
            self.logger.info(
                "%s: participant '%s' not in case '%s' — skipping (idempotent)",
                self.name,
                self.participant_id,
                self.case_id,
            )
            return Status.SUCCESS

        case.remove_participant(self.participant_id)
        self.datalayer.save(case)
        self.logger.info(
            "%s: removed participant '%s' from case '%s'",
            self.name,
            self.participant_id,
            self.case_id,
        )
        return Status.SUCCESS
