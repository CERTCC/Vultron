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

"""Condition nodes for case, embargo, and participant validation."""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerCondition
from vultron.core.models.protocols import (
    is_case_model,
    is_participant_model,
)


class ValidateCaseExistsNode(DataLayerCondition):
    """Check that the target case exists in the DataLayer.

    Returns SUCCESS if the case is found and passes ``is_case_model``.
    Returns FAILURE otherwise, halting the parent Sequence.
    """

    def __init__(self, case_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = (
                f"Case '{self.case_id}' not found or not a valid case model"
            )
            self.logger.warning(
                "ValidateCaseExists: %s", self.feedback_message
            )
            return Status.FAILURE

        return Status.SUCCESS


class IsActiveEmbargoNode(DataLayerCondition):
    """Check that the given embargo is the active embargo on the case.

    Returns SUCCESS if ``case.active_embargo`` resolves to ``embargo_id``.
    Returns FAILURE if the embargo is not active (e.g. it was only proposed),
    halting the parent Sequence so the teardown path is skipped.
    """

    def __init__(self, case_id: str, embargo_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{self.case_id}' not found"
            return Status.FAILURE

        active = case.active_embargo
        active_id = (
            active if isinstance(active, str) else getattr(active, "id_", None)
        )
        if active_id != self.embargo_id:
            self.feedback_message = (
                f"Embargo '{self.embargo_id}' is not the active embargo"
                f" on case '{self.case_id}'"
            )
            return Status.FAILURE

        return Status.SUCCESS


class LookupParticipantNode(DataLayerCondition):
    """Resolve participant from case and actor_id.

    Looks up the actor in case.actor_participant_index and reads the
    participant record. Stores the participant record on the blackboard
    under the 'participant' key for downstream nodes to use.

    Returns SUCCESS if participant is found, FAILURE otherwise.
    """

    def __init__(
        self,
        case_id: str,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="participant", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        actor_id = self.actor_id
        if actor_id is None:
            self.feedback_message = "actor_id not found in blackboard"
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        participant_id = case.actor_participant_index.get(actor_id)
        if not participant_id:
            self.feedback_message = (
                f"No participant found for actor '{actor_id}'"
                f" on case '{self.case_id}'"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        participant = self.datalayer.read(participant_id)
        if not is_participant_model(participant):
            self.feedback_message = (
                f"Participant '{participant_id}' not found or invalid"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.blackboard.participant = participant
        self.feedback_message = (
            f"Resolved participant '{participant_id}' for actor"
            f" '{actor_id}' on case '{self.case_id}'"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class OptionalLookupParticipantNode(DataLayerCondition):
    """Optionally resolve participant from case and actor_id.

    Lenient variant of LookupParticipantNode: returns SUCCESS even when the case
    or participant is not found. This allows the BT to continue with downstream
    PEC updates (which are then skipped) so that protocol-visible operations
    (log cascade) can still succeed even if the participant doesn't exist on this
    peer.

    Stores the participant record on the blackboard 'participant' key if found,
    or does nothing if case/participant missing. Always returns SUCCESS so the
    tree continues to cascade the log entry to all peers (idempotent behavior).

    Used in received-side BT workflows where participant may legitimately not
    exist locally yet.
    """

    def __init__(
        self,
        case_id: str,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="participant", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None:
            return Status.SUCCESS

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{self.case_id}' not found — skipping participant lookup"
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        actor_id = self.actor_id
        if actor_id is None:
            self.feedback_message = "actor_id not found in blackboard — skipping participant lookup"
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        participant_id = case.actor_participant_index.get(actor_id)
        if not participant_id:
            self.feedback_message = (
                f"No participant found for actor '{actor_id}'"
                f" on case '{self.case_id}' — skipping PEC update"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        participant = self.datalayer.read(participant_id)
        if not is_participant_model(participant):
            self.feedback_message = (
                f"Participant '{participant_id}' not found or invalid"
                " — skipping PEC update"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        self.blackboard.participant = participant
        self.feedback_message = (
            f"Resolved participant '{participant_id}' for actor"
            f" '{actor_id}' on case '{self.case_id}'"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS
