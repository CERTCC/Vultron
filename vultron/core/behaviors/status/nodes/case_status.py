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

Contains the idempotency guard, all-or-nothing transition validator, and
append node implementing the AddCaseStatusToCase BT sequence (issue #758).

Per-dimension adjudication nodes (RSH-05, ADR-0061, ISSUE-2256) live in
:mod:`cs_dimension_filter` to keep this module under the 500-line limit.
"""

import logging
from typing import Any

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.behaviors.status.nodes.cs_dimension_filter import (
    BB_CASE_STATUS_DIM_FILTER,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.protocols import PersistableModel
from vultron.core.states.cs import is_valid_pxa_transition
from vultron.core.states.em import is_valid_em_transition

logger = logging.getLogger(__name__)

# Stable sentinel used as feedback_message when a CaseStatus duplicate is
# detected.  The use case imports this constant to distinguish idempotent
# no-ops (log at INFO) from real failures (log at WARNING).
CASE_STATUS_ALREADY_PRESENT = "case_status_already_present"


class CheckCaseStatusIdempotencyNode(
    SilentIdempotencyGuardMixin, DataLayerConditionWithPorts
):
    """AC-1: Verify the CaseStatus has not already been added to the case.

    Returns FAILURE with ``feedback_message == CASE_STATUS_ALREADY_PRESENT``
    when *status_id* is already in ``case.case_statuses`` — a benign no-op
    with no ledger write (CLP-13-001, CLP-13-002).

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
            return self._idempotent_failure(
                self.logger,
                "CheckCaseStatusIdempotency: status '%s' already in case '%s'"
                " — skipping (idempotent, CLP-13-001)",
                self.status_id,
                self.case_id,
            )

        return Status.SUCCESS


class ValidateCaseStatusTransitionNode(DataLayerConditionWithPorts):
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

        em_dim = getattr(status_obj, "em", None)
        pxa_dim = getattr(status_obj, "pxa", None)
        if not self._check_transition(
            "EM",
            current_status.em.state,
            em_dim.state if em_dim is not None else None,
            is_valid_em_transition,
        ):
            return Status.FAILURE

        if not self._check_transition(
            "PXA",
            current_status.pxa.state,
            pxa_dim.state if pxa_dim is not None else None,
            is_valid_pxa_transition,
        ):
            return Status.FAILURE

        return Status.SUCCESS


class AppendCaseStatusToCaseNode(DataLayerActionWithPorts):
    """Append the resolved CaseStatus to ``case.case_statuses`` and persist.

    When ``BB_CASE_STATUS_DIM_FILTER`` carries a filtered status for this
    tick (written by :class:`FinalizeCsFilterNode`), that filtered object is
    appended and saved to the DataLayer so the canonical record reflects the
    accepted portion, not the raw assertion (RSH-05, ISSUE-2256).

    Falls back to resolving from the DataLayer/fallback when no filter is
    present (original behavior for unfiltered statuses).

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

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        return {
            **super().input_ports(),
            BB_CASE_STATUS_DIM_FILTER: PortInformation(
                data_type=object, required=False
            ),
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            BB_CASE_STATUS_DIM_FILTER: f"/{BB_CASE_STATUS_DIM_FILTER}",
        }

    def _resolve_filtered(self) -> CaseStatus | None:
        """Return the filter-adjusted CaseStatus if one exists for this tick."""
        payload = self._try_get_input(BB_CASE_STATUS_DIM_FILTER)
        if not isinstance(payload, dict):
            return None
        if payload.get("status_id") != self.status_id:
            return None
        obj = payload.get("filtered_status")
        return obj if isinstance(obj, CaseStatus) else None

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

        # Use the per-dimension-filtered status when available; otherwise fall
        # back to the raw asserted object (no filtering was needed or applied).
        status_obj: CaseStatus | PersistableModel | None = (
            self._resolve_filtered()
        )
        if status_obj is not None:
            self.datalayer.save(status_obj)
        else:
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
        case.add_case_status(status_obj)
        self.datalayer.save(case)
        self.logger.info(
            "AppendCaseStatusToCase: added status '%s' to case '%s'",
            self.status_id,
            self.case_id,
        )
        return Status.SUCCESS
