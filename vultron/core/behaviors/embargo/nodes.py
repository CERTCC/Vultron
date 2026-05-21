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

"""
BT nodes for receive-side embargo lifecycle workflows.

Implements the receiver-side embargo teardown workflow triggered by receipt
of an ``Announce(EmbargoEvent)`` activity from a Case Actor:

    AnnounceEmbargoTeardownBT (Sequence)
    ├─ ValidateCaseExistsNode     # case must be found and pass is_case_model
    └─ ApplyEmbargoTeardownNode   # ACTIVE→EXITED, clear embargo, reset PEC

Per specs/behavior-tree-integration.yaml BT-06-001.
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.models.protocols import is_case_model
from vultron.core.states.em import EM, is_valid_em_transition

logger = logging.getLogger(__name__)


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


class ApplyEmbargoTeardownNode(DataLayerAction):
    """Apply receiver-side embargo teardown.

    Performs the ACTIVE/REVISE → EXITED EM state transition, clears
    ``active_embargo``, and resets all participant embargo consent states.
    Handles idempotency: if EM state is already EXITED, logs and returns
    SUCCESS without modifying the DataLayer.

    For unexpected EM states a state-sync override is applied (the sender
    is authoritative) with a WARNING log entry, mirroring the pattern used
    by ``AddEmbargoEventToCaseReceivedUseCase``.
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
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning(
                "ApplyEmbargoTeardown: %s", self.feedback_message
            )
            return Status.FAILURE

        current_em = case.current_status.em_state

        if current_em == EM.EXITED:
            self.feedback_message = (
                f"Case '{self.case_id}' EM already EXITED — idempotent no-op"
            )
            self.logger.info("ApplyEmbargoTeardown: %s", self.feedback_message)
            return Status.SUCCESS

        if not is_valid_em_transition(current_em, EM.EXITED):
            self.logger.warning(
                "ApplyEmbargoTeardown: EM transition %s → EXITED is not a"
                " standard machine transition for case '%s';"
                " applying state-sync override",
                current_em,
                self.case_id,
            )

        case.current_status.em_state = EM.EXITED
        case.active_embargo = None  # type: ignore[attr-defined]

        # Reset all participants' embargo consent state to NO_EMBARGO.
        # Lazy import avoids a direct dependency on the received use-case
        # module from within the BT node layer.
        from vultron.core.use_cases.received.embargo import (
            _reset_case_participant_embargo_consent,
        )

        _reset_case_participant_embargo_consent(self.datalayer, case)
        self.datalayer.save(case)

        self.feedback_message = (
            f"Embargo teardown applied on case '{self.case_id}'"
            f" (EM {current_em} → EXITED)"
        )
        self.logger.info("ApplyEmbargoTeardown: %s", self.feedback_message)
        return Status.SUCCESS
