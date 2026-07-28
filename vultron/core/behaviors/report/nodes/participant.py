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

"""Participant RM transition nodes for the report behavior tree."""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import update_participant_rm_state


class TransitionParticipantRMtoAccepted(DataLayerAction):
    """
    Transition actor's RM state to ACCEPTED in the specified case.

    Finds the actor's CaseParticipant in case.case_participants, appends a
    new ParticipantStatus with rm_state=RM.ACCEPTED, and persists the
    updated case to the DataLayer.

    Called when an actor engages a case (receives RmEngageCaseActivity /
    Join(VulnerabilityCase)).
    """

    def __init__(self, case_id: str, actor_id: str, name: str | None = None):
        """
        Initialize TransitionParticipantRMtoAccepted node.

        Args:
            case_id: ID of VulnerabilityCase
            actor_id: ID of Actor whose RM state transitions to ACCEPTED
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.actor_id = actor_id

    def update(self) -> Status:
        """
        Append ParticipantStatus(rm_state=ACCEPTED) to actor's CaseParticipant.

        Returns:
            SUCCESS if transition persisted, FAILURE on error
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            if self.actor_id is None:
                self.logger.error(f"{self.name}: actor_id not available")
                return Status.FAILURE
            result = update_participant_rm_state(
                self.case_id, self.actor_id, RM.ACCEPTED, self.datalayer
            )
            return Status.SUCCESS if result else Status.FAILURE
        except Exception as e:
            self.logger.error(f"Error updating participant RM state: {e}")
            return Status.FAILURE


class TransitionParticipantRMtoDeferred(DataLayerAction):
    """
    Transition actor's RM state to DEFERRED in the specified case.

    Finds the actor's CaseParticipant in case.case_participants, appends a
    new ParticipantStatus with rm_state=RM.DEFERRED, and persists the
    updated case to the DataLayer.

    Called when an actor defers a case (receives RmDeferCaseActivity /
    Ignore(VulnerabilityCase)).
    """

    def __init__(self, case_id: str, actor_id: str, name: str | None = None):
        """
        Initialize TransitionParticipantRMtoDeferred node.

        Args:
            case_id: ID of VulnerabilityCase
            actor_id: ID of Actor whose RM state transitions to DEFERRED
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.actor_id = actor_id

    def update(self) -> Status:
        """
        Append ParticipantStatus(rm_state=DEFERRED) to actor's CaseParticipant.

        Returns:
            SUCCESS if transition persisted, FAILURE on error
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            if self.actor_id is None:
                self.logger.error(f"{self.name}: actor_id not available")
                return Status.FAILURE
            result = update_participant_rm_state(
                self.case_id, self.actor_id, RM.DEFERRED, self.datalayer
            )
            return Status.SUCCESS if result else Status.FAILURE
        except Exception as e:
            self.logger.error(f"Error updating participant RM state: {e}")
            return Status.FAILURE
