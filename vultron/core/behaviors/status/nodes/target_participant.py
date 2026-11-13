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

"""Guard: the receiver holds the target participant, in the tree's case."""

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.case_lookup import CaseResolving
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant


class TargetParticipantInCaseNode(CaseResolving, DataLayerConditionWithPorts):
    """Door: the target participant's stored record names *case_id*.

    An ``Add(ParticipantStatus)`` acts on the case of the participant it
    targets, as the receiver recorded it (HP-08-008).  When the receiver
    holds no record of that participant, or the record names another case
    or none, the activity has no case to act on, and this door refuses it
    ahead of the sender guard, so nothing is written or sent (HP-08-014,
    HP-01-006).  The tree is scoped to the case the activity names, so its
    path stage can judge the receiver; this door is what keeps a case the
    target is not recorded in from ever taking the status (HP-08-008).  A
    pure read, run as the tree's ``case_resolution`` step.
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
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        record = self.datalayer.read(self.participant_id)
        if not isinstance(record, CaseParticipant):
            self.feedback_message = (
                f"this receiver holds no record of target participant"
                f" '{self.participant_id}' — REFUSED (HP-08-014)"
            )
        else:
            context = _as_id(record.context)
            if context and context == self.case_id:
                return Status.SUCCESS
            self.feedback_message = (
                f"target participant '{self.participant_id}' belongs to case"
                f" '{context}', not case '{self.case_id}' — REFUSED (HP-08-014)"
                if context
                else f"target participant '{self.participant_id}' names no"
                " case — REFUSED (HP-08-014)"
            )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


__all__ = ["TargetParticipantInCaseNode"]
