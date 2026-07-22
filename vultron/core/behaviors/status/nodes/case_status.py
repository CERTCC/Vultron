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

"""Case status workflow nodes for AddCaseStatusToCase.

Contains the idempotency guard, EM/PXA transition validation, and append
nodes implementing the AddCaseStatusToCase BT sequence (issue #758).
"""

import logging
from typing import Any

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.protocols import PersistableModel
from vultron.core.states.cs import is_valid_pxa_transition
from vultron.core.states.em import is_valid_em_transition
from vultron.core.models._helpers import _as_id

logger = logging.getLogger(__name__)

# Stable sentinel used as feedback_message when a CaseStatus duplicate is
# detected.  The use case imports this constant to distinguish idempotent
# no-ops (log at INFO) from real failures (log at WARNING).
CASE_STATUS_ALREADY_PRESENT = "case_status_already_present"


class CheckCaseStatusIdempotencyNode(DataLayerCondition):
    """AC-1: Verify the CaseStatus has not already been added to the case.

    Returns FAILURE with ``feedback_message == CASE_STATUS_ALREADY_PRESENT``
    when *status_id* is already in ``case.case_statuses`` — a benign no-op.

    Returns FAILURE with a distinct message when the case itself is not found.

    Returns SUCCESS when the status is not yet present and the Sequence should
    continue.

    Per issue #758 AC-1.
    """

    def __init__(
        self,
        case_id: str,
        status_id: str,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.status_id = status_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning(
                "CheckCaseStatusIdempotency: %s", self.feedback_message
            )
            return Status.FAILURE

        existing_ids = [_as_id(s) for s in case.case_statuses]
        if self.status_id in existing_ids:
            self.feedback_message = CASE_STATUS_ALREADY_PRESENT
            self.logger.debug(
                "CheckCaseStatusIdempotency: status '%s' already in case '%s'"
                " — skipping (idempotent)",
                self.status_id,
                self.case_id,
            )
            return Status.FAILURE

        return Status.SUCCESS


class ValidateCaseStatusTransitionNode(DataLayerCondition):
    """AC-2: Validate that the new CaseStatus represents a legal state transition.

    Uses ``case.current_status`` as the reference point.  When the case has no
    current status (first status ever), the transition is unconditionally
    allowed.  Otherwise both the EM state and PXA state transitions are
    validated independently.

    Returns SUCCESS when the transition is valid (or there is no prior status).
    Returns FAILURE when an invalid EM or PXA transition is detected.

    Per issue #758 AC-2.
    """

    def __init__(
        self,
        case_id: str,
        status_id: str,
        status_obj_fallback: PersistableModel | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.status_id = status_id
        self.status_obj_fallback = status_obj_fallback

    def _resolve_status(self) -> object | None:
        assert self.datalayer is not None
        status_obj = self.datalayer.read(self.status_id)
        if hasattr(status_obj, "id_"):
            return status_obj
        return self.status_obj_fallback

    def _check_transition(
        self,
        label: str,
        current: object,
        new: object,
        validator: Any,
    ) -> bool:
        if new is None or current == new:
            return True
        if validator(current, new):
            return True
        self.feedback_message = (
            f"Invalid {label} transition {current} → {new}"
            f" for case '{self.case_id}'"
        )
        self.logger.warning(
            "ValidateCaseStatusTransition: %s — rejecting",
            self.feedback_message,
        )
        return False

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning(
                "ValidateCaseStatusTransition: %s", self.feedback_message
            )
            return Status.FAILURE

        try:
            current_status = case.current_status
        except ValueError:
            return Status.SUCCESS

        status_obj = self._resolve_status()
        if status_obj is None:
            self.feedback_message = f"Status '{self.status_id}' not found"
            self.logger.warning(
                "ValidateCaseStatusTransition: %s", self.feedback_message
            )
            return Status.FAILURE

        if not self._check_transition(
            "EM",
            current_status.em_state,
            getattr(status_obj, "em_state", None),
            is_valid_em_transition,
        ):
            return Status.FAILURE

        if not self._check_transition(
            "PXA",
            current_status.pxa_state,
            getattr(status_obj, "pxa_state", None),
            is_valid_pxa_transition,
        ):
            return Status.FAILURE

        return Status.SUCCESS


class AppendCaseStatusToCaseNode(DataLayerAction):
    """Append the resolved CaseStatus to ``case.case_statuses`` and persist.

    Resolves the status object from the DataLayer first; if not found there,
    saves the inline fallback and re-reads so the stored canonical record is
    used.

    Returns SUCCESS on successful append.
    Returns FAILURE if the case or status cannot be resolved.

    Per issue #758 AC-1.
    """

    def __init__(
        self,
        case_id: str,
        status_id: str,
        status_obj_fallback: PersistableModel | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.status_id = status_id
        self.status_obj_fallback = status_obj_fallback

    def _resolve_status(self) -> "PersistableModel | None":
        assert self.datalayer is not None
        status_obj = self.datalayer.read(self.status_id)
        if hasattr(status_obj, "id_"):
            return status_obj
        status_obj = self.status_obj_fallback
        if status_obj is not None:
            self.datalayer.save(status_obj)
            status_obj = self.datalayer.read(self.status_id) or status_obj
        return status_obj if hasattr(status_obj, "id_") else None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning(
                "AppendCaseStatusToCase: %s", self.feedback_message
            )
            return Status.FAILURE

        status_obj = self._resolve_status()
        if status_obj is None:
            self.feedback_message = f"Status '{self.status_id}' not found"
            self.logger.warning(
                "AppendCaseStatusToCase: %s", self.feedback_message
            )
            return Status.FAILURE

        if not isinstance(status_obj, CaseStatus):
            self.feedback_message = (
                f"Status '{self.status_id}' is not a CaseStatus"
            )
            self.logger.warning(
                "AppendCaseStatusToCase: %s", self.feedback_message
            )
            return Status.FAILURE
        case.case_statuses.append(status_obj)
        self.datalayer.save(case)
        self.logger.info(
            "AppendCaseStatusToCase: added status '%s' to case '%s'",
            self.status_id,
            self.case_id,
        )
        return Status.SUCCESS
